import os
import sys
from platform import system
from PyQt6 import uic, QtWidgets
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QMainWindow, QApplication, QStyleFactory
from PyQt6.QtCore import QThread, QObject
import requests
from bs4 import BeautifulSoup
import csv
from multiprocessing.pool import ThreadPool
from peewee import *

DOMAIN = 'https://www.firmy.cz'


if system() == "Windows":
    appFolder = os.path.dirname(os.path.realpath(sys.argv[0])) + "\\"
elif system() == "Linux":
    appFolder = os.path.dirname(os.path.realpath(sys.argv[0])) + "//"

dbp = SqliteDatabase('database.db')


class ListCategory(Model):
    name = TextField()
    link = TextField(primary_key=True)

    class Meta:
        db_table = 'category'
        database = dbp


def create_id():
    i = 0

    def func():
        nonlocal i
        i += 1
        return i

    return func


class Catalog(QThread):
    stepFindCards = pyqtSignal(int)
    finishFindCards = pyqtSignal()
    stepChanged = pyqtSignal(list)
    finished = pyqtSignal()
    error = pyqtSignal()

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.id = create_id()

    def run(self):
        def write_csv(data):
            with open('firmy.csv', 'a', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([data['phone'],
                                 data['mail']])

        def get_html(url):
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/50.0.2661.102 Safari/537.36'}
            r = requests.get(url, headers)
            return r.content

        def get_cards(html):
            soup = BeautifulSoup(html, 'html.parser')
            cards = soup.find_all('div', class_='premiseBox')
            return cards

        def card_data(cards):
            href = cards.find('h3').find('a').get('href')
            html = get_html(href)
            soup = BeautifulSoup(html, 'html.parser')
            try:
                phone = soup.find('div', class_='value detailPhone detailPhonePrimary').find("span").text
            except:
                phone = ''
            try:
                mail = soup.find('div', class_='value detailEmail').text.strip()
            except:
                mail = ''
            data = {'name': '',
                    'phone': phone,
                    'mail': mail}

            write_csv(data)
            self.stepChanged.emit([str(self.id()), data['phone'], data['mail']])

        def get_main_data(url):
            all_cards = []
            page_number = 1
            link = url

            while True:
                try:
                    cards = get_cards(get_html(url))
                except:
                    self.error.emit()
                if cards:
                    all_cards.extend(cards)
                    self.stepFindCards.emit(len(all_cards))
                    page_number += 1
                    url = f'{link}?page={page_number}'
                else:
                    self.finishFindCards.emit()
                    break

                # time.sleep(0.3)
            pool = ThreadPool(10)

            pool.map(card_data, all_cards)
            pool.close()
            pool.join()

        get_main_data(self.url)

        self.finished.emit()


class Category(QObject):
    finished = pyqtSignal()

    def __init__(self, url):
        super().__init__()
        self.url = url
        self.id = create_id()

    def run(self):
        def db():
            dbp.create_tables([ListCategory])
            ListCategory.truncate_table()

        def write_data_to_db(data):
            with dbp.atomic():
                ListCategory.create(**data)

        def get_html(url):
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/50.0.2661.102 Safari/537.36'}
            r = requests.get(url, headers)
            return r.content

        def get_list_category(html):
            soup = BeautifulSoup(html, 'html.parser')
            categorys = soup.find_all('li', class_='item link')
            return categorys

        def get_category(soup):
            name = soup.find('h3').find('a').text.strip()
            link = soup.find('h3').find('a').get('href')
            data = {'name': name,
                    'link': link}
            write_data_to_db(data)

        def get_subcategory(sub):
            name = sub.find('a').text.strip()
            url = sub.find('a').get('href')

            data = {'name': name,
                    'link': url}
            write_data_to_db(data)

        def get_menu(url):
            categorys = get_list_category(get_html(url))

            for cat in categorys:
                get_category(cat)
                subcategory = cat.find_all('h4')
                for sub in subcategory:
                    get_subcategory(sub)

        db()
        get_menu(self.url)

        self.finished.emit()


class App(QMainWindow):
    def __init__(self):
        """Constructor."""
        super(App, self).__init__()
        uic.loadUi(appFolder + "Parser_v2.ui", self)  # Load the UI(User Interface) file.
        # self.makeWindowCenter()
        self.tableWidget.setHorizontalHeaderLabels(
            ["id", "phone", "mail"])
        self.tableWidget.verticalHeader().hide()
        self.tableWidget.setAlternatingRowColors(True)
        self.tableWidget.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.thread = None
        self.thread1 = None
        self.category_list = None
        self.combobox_add()
        self.label_8.hide()
        self.label_9.hide()
        self.run_system()
        self.statusBar().showMessage("Scraper for website")
        self.setWindowTitle("App for scrape data from https://www.firmy.cz")

    def make_window_center(self):
        """For launching windows in center."""
        qt_rectangle = self.frameGeometry()

        self.move(qt_rectangle.topLeft())

    def run_system(self):
        """Main load function"""

        self.pushButton.clicked.connect(self.get_category)
        self.pushButton_3.clicked.connect(self.start_button)

    def combobox_add(self):
        try:
            dbp.connect()
            for category in ListCategory.select():
                self.comboBox.addItem(category.name)
            dbp.close()
        except:
            pass

    def get_category(self):
        if self.thread1 is None:
            self.thread1 = Category(DOMAIN)
            self.thread1.finished.connect(self.cat_finished)
            self.thread1.run()
        else:
            self.thread1 = None

    def start_button(self):

        if self.thread is None:
            self.tableWidget.setRowCount(0)
            name = self.comboBox.currentText()

            url = ListCategory.select().where(ListCategory.name == name).get()
            if url:
                self.thread = Catalog(url)
                self.thread.stepFindCards.connect(self.on_step_find_card)
                self.thread.finishFindCards.connect(self.on_finished_find_card)

                self.thread.stepChanged.connect(self.on_step_changed)
                self.thread.finished.connect(self.on_finished)
                self.thread.error.connect(self.error)
                self.thread.start()

                self.pushButton_3.setText("Stop")
                self.pushButton_3.setEnabled(False)
                self.statusBar().showMessage("Please wait.....")
            else:
                self.thread = None
                self.pushButton_3.setText("Start")
                self.pushButton_3.setEnabled(True)
        else:
            self.thread.terminate()
            self.thread = None
            self.pushButton_title.setText("Start")
            self.pushButton_3.setEnabled(True)

    def on_step_find_card(self, int):
        self.label_8.show()
        self.label_9.show()
        self.label_9.setText(f'Find {int} cards')

    def on_finished_find_card(self):
        self.label_8.hide()

    def on_step_changed(self, data):
        rowPosition = self.tableWidget.rowCount()
        self.tableWidget.insertRow(rowPosition)
        for i in range(3):
            self.tableWidget.setItem(rowPosition, i, QtWidgets.QTableWidgetItem(data[i]))

    def on_finished(self):
        self.thread = None

        self.pushButton_3.setText("Start")
        self.pushButton_3.setEnabled(True)
        self.statusBar().showMessage('App for scrape data from https://www.firmy.cz')
        QtWidgets.QMessageBox.information(None, "Info", "Please, get csv file in folder with programm")

    def error(self):
        self.thread.terminate()
        self.thread = None

        self.pushButton_3.setText("Start")
        self.pushButton_3.setEnabled(True)
        self.statusBar().showMessage('App for scrape data from https://www.firmy.cz')
        QtWidgets.QMessageBox.information(None, "Info", "Please, input correct URL")

    def cat_step_changed(self, data):
        pass

    def cat_finished(self):
        dbp.close()
        QtWidgets.QMessageBox.information(None, "Info", "Succesfull get category")
        self.thread1 = None
        self.combobox_add()

    def cat_error(self):
        pass


if __name__ == '__main__':
    app = QApplication(sys.argv)

    app.setStyle(QStyleFactory.create("Fusion"))

    run_main = App()
    run_main.show()
    sys.exit(app.exec())
