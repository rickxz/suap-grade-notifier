from decouple import config
from time import sleep
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import schedule
import pywhatkit
import os.path

def acessa_suap(driver):
    driver.get('https://suap.ifsp.edu.br/accounts/login/?next=/')
    username_input = driver.find_element(By.ID, 'id_username')
    username_input.send_keys(config('USER'))

    password_input = driver.find_element(By.ID, 'id_password')
    password_input.send_keys(config('PASSWORD'))
    password_input.send_keys(Keys.ENTER)
    sleep(1)


def get_notas(driver):
    prontuario = config('USER')
    driver.get(f'https://suap.ifsp.edu.br/edu/aluno/{prontuario}/?tab=boletim')
    sleep(5)
    grade_table = driver.find_elements(By.CSS_SELECTOR, "tr[class^=' matricula_periodo_agrupamento']")
    notas = None
    if verifica_arquivo():  
        with open('notas.csv', 'r', encoding='utf-8') as arquivo_read:
            notas = list(csv.reader(arquivo_read))
    else:
        with open('notas.csv', 'w', encoding='utf-8', newline='') as arquivo_write:
            w = csv.writer(arquivo_write)
            for materia in grade_table:
                linha = []
                materia = materia.find_elements(By.TAG_NAME, 'td')
                nome_materia = materia[2].get_attribute('innerHTML')
                nome_materia = nome_materia[nome_materia.rfind('-') + 2: len(nome_materia) - 1]
                linha.append(nome_materia)
                for i in range(9, 17):
                    if i % 2 != 0: # pega somente as notas
                        linha.append(materia[i].get_attribute('innerHTML'))
                if notas != None:
                    if not linha in notas:
                        envia_mensagem(f'A nota de {linha[0].title()} mudou!!')

                w.writerow(linha)


def envia_mensagem(mensagem):
    id_grupo = config('ID_GRUPO')
    pywhatkit.sendwhatmsg_to_group_instantly(id_grupo, mensagem)


def verifica_arquivo():
    if os.path.isfile('notas.csv'):
        return True
    return False

driver = webdriver.Chrome()
acessa_suap(driver)
get_notas(driver)
sleep(5)
schedule.every(5).seconds.do(get_notas, driver)

while True:
    schedule.run_pending()
    sleep(5)