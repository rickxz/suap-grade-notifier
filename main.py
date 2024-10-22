from decouple import config
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver 
from pymongo.mongo_client import MongoClient
from cryptography.fernet import Fernet


client = MongoClient(config('MONGODB_URI'))
fernet = Fernet(config("HASH_KEY").encode())
users_collection = client['suap-grade-notifier']['user-grades']
users = users_collection.find()

def acessa_suap(driver: WebDriver, prontuary: str, password: str):
    driver.get('https://suap.ifsp.edu.br/accounts/login/?next=/')
    username_input = driver.find_element(By.ID, 'id_username')
    username_input.send_keys(prontuary)

    password_input = driver.find_element(By.ID, 'id_password')
    password_input.send_keys(password)
    password_input.send_keys(Keys.ENTER)
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(EC.visibility_of_element_located((By.XPATH, "/html/body/div[1]/aside/nav/ul[1]/li[1]/a/span[2]")))
    except TimeoutException:
        driver.find_element(By.XPATH, "/html/body/div[1]/a/span[1]").click()


def iterate_subjects(driver: WebDriver, prontuary: str):
    driver.get(f'https://suap.ifsp.edu.br/edu/aluno/{prontuary.upper()}/?tab=boletim')
    wait = WebDriverWait(driver, 10)
    wait.until(EC.visibility_of_all_elements_located((By.CSS_SELECTOR, "table[id^='tabela_boletim'] > tbody tr")))
    class_subjects = driver.find_elements(By.CSS_SELECTOR, "table[id^='tabela_boletim'] > tbody tr")

    grades_dict = {}
    for subject in class_subjects:
        line = []
        subject_columns = subject.find_elements(By.TAG_NAME, 'td')
        subject_name = subject_columns[1].get_attribute('innerHTML')
        subject_name = subject_name[subject_name.rfind('-') + 2: len(subject_name) - 1]
        line.append(subject_name)

        detail_button = subject_columns[-1].find_element(By.TAG_NAME, 'a')
        detail_button.click()
        grades_dict[subject_name] = {}
        get_grades(driver, subject_name, grades_dict)
        driver.find_element(By.CSS_SELECTOR, "div.tclose").click()

    return grades_dict

    

def get_grades(driver: WebDriver, subject_name: str, grades_dict: dict):
    wait = WebDriverWait(driver, 10)
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.tinner .borda:first-of-type > tbody > tr")))
    grades_rows = driver.find_elements(By.CSS_SELECTOR, ".tinner .borda:first-of-type > tbody > tr")
    for row in grades_rows:
        columns = row.find_elements(By.TAG_NAME, 'td')
        assessment_name = columns[0].get_attribute('innerHTML')
        grade = columns[-1].get_attribute('innerHTML')
        print(f'{subject_name} | {assessment_name}: {grade}')
        grades_dict[subject_name][assessment_name] = grade


def compare_grades(user_prontuary: str, previous_grades: dict, current_grades: dict):
    if previous_grades == current_grades: return

    for subject_prev, subject_curr in zip(previous_grades, current_grades):
        prev_grades = previous_grades[subject_prev]
        curr_grades = current_grades[subject_curr]
        for prev_grade, curr_grade in zip(prev_grades, curr_grades):
            if prev_grades[prev_grade] != curr_grades[curr_grade]:
                print('a nota mudou!')

    filter = {'prontuary': user_prontuary }
    new_values = {"$set": {'grades': current_grades}}

    users_collection.update_one(filter, new_values)
    print('usuario atualizado com sucesso!')

for user in users:
    driver = webdriver.Edge()
    password_decrypted = fernet.decrypt(user['password'].encode()).decode()
    acessa_suap(driver, user['prontuary'], password_decrypted)
    current_grades_dict = {}
    current_grades_dict = iterate_subjects(driver, user['prontuary'])
    previous_grades_dict = user.get('grades') or {}
    compare_grades(user['prontuary'], previous_grades_dict, current_grades_dict)
 
    driver.close()