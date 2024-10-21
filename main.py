from decouple import config
import csv
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver 
import os.path
from pymongo.mongo_client import MongoClient


client = MongoClient(config('MONGODB_URI'))

def acessa_suap(driver: WebDriver):
    driver.get('https://suap.ifsp.edu.br/accounts/login/?next=/')
    username_input = driver.find_element(By.ID, 'id_username')
    username_input.send_keys(config('USER'))

    password_input = driver.find_element(By.ID, 'id_password')
    password_input.send_keys(config('PASSWORD'))
    password_input.send_keys(Keys.ENTER)
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.visibility_of_element_located((By.XPATH, "/html/body/div[1]/aside/nav/ul[1]/li[1]/a/span[2]")))
    except TimeoutException:
        driver.find_element(By.XPATH, "/html/body/div[1]/a/span[1]").click()


def iterate_subjects(driver: WebDriver):
    prontuario = config('USER')
    driver.get(f'https://suap.ifsp.edu.br/edu/aluno/{prontuario.upper()}/?tab=boletim')
    wait = WebDriverWait(driver, 10)
    wait.until(EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "table[id^='tabela_boletim'] > tbody tr")))
    class_subjects = driver.find_elements(By.CSS_SELECTOR, "table[id^='tabela_boletim'] > tbody tr")
    notas = None
    if verifica_arquivo():  
        with open('notas.csv', 'r', encoding='utf-8') as arquivo_read:
            notas = list(csv.reader(arquivo_read))
    for subject in class_subjects:
        line = []
        subject_columns = subject.find_elements(By.TAG_NAME, 'td')
        subject_name = subject_columns[1].get_attribute('innerHTML')
        subject_name = subject_name[subject_name.rfind('-') + 2: len(subject_name) - 1]
        line.append(subject_name)

        detail_button = subject_columns[-1].find_element(By.TAG_NAME, 'a')
        detail_button.click()
        get_grades(driver, subject_name)
        driver.find_element(By.CSS_SELECTOR, "div.tclose").click()

def get_grades(driver: WebDriver, subject_name):
    wait = WebDriverWait(driver, 10)
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.tinner .borda:first-of-type > tbody > tr")))
    grades_rows = driver.find_elements(By.CSS_SELECTOR, ".tinner .borda:first-of-type > tbody > tr")
    for row in grades_rows:
        columns = row.find_elements(By.TAG_NAME, 'td')
        assessment_name = columns[0].get_attribute('innerHTML')
        grade = columns[-1].get_attribute('innerHTML')
        print(f'{subject_name} | {assessment_name}: {grade}')


def verifica_arquivo():
    if os.path.isfile('notas.csv'):
        return True
    return False

driver = webdriver.Chrome()
acessa_suap(driver)
iterate_subjects(driver)
driver.close()