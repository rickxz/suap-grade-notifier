## 🏁 Comece

- Sabendo que o sistema do SUAP (Sistema Unificado de Administração Pública) é horripilante e não possui um sistema de notificação para quando notas novas são enviadas ao sistema, eu criei um script de uso pessoal que realiza esse trabalho.

```shell
$ git clone https://github.com/rickxz/suap-grade-notifier
$ cd suap-grade-notifier
```

#

## ⚙️ Configurar variáveis de ambiente (.env)

- USER: Seu prontuário de login do SUAP
- PASSWORD: Sua senha do SUAP
- ID_GRUPO: ID do grupo do Whatsapp que deseja enviar a mensagem notificando a mudança de notas

#

## 📚 Principais bibliotecas utilizadas

- csv
- selenium
- pywhatkit
- schedule