# SUAP Grade Notifier

O SUAP não avisa o estudante quando uma nota é lançada. Este projeto verifica o boletim do SUAP do IFSP periodicamente e mostra uma notificação do Windows quando algo muda.

## O que é notificado

- Nota nova ou alterada em uma avaliação (o detalhamento do botão "Detalhar": A1, A2, Prova…)
- Mudança nas médias do boletim (N1, MD, NAF, MFD)
- Mudança de situação (ex.: Cursando → Aprovado)
- Novas faltas

Várias mudanças na mesma verificação viram uma única notificação. Clicar nela abre o boletim no navegador.

## Requisitos

- Windows 10 ou 11 com o Microsoft Edge (já vem instalado)
- Python 3.11 ou mais recente ([python.org](https://www.python.org/downloads/) ou `winget install Python.Python.3.14`)
- Uma conta de estudante no [SUAP do IFSP](https://suap.ifsp.edu.br)

## Instalação

No PowerShell:

```powershell
git clone https://github.com/rickxz/suap-grade-notifier.git
cd suap-grade-notifier
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

O instalador:

1. cria um ambiente Python em `%LOCALAPPDATA%\suap-notifier`;
2. pede seu prontuário e sua senha, faz um login de teste e salva o boletim atual como ponto de partida (sem notificar);
3. agenda uma tarefa no Agendador de Tarefas do Windows que roda ao entrar no Windows e a cada 30 minutos.

Não é preciso deixar nenhum terminal aberto.

## Como funciona

- O login do SUAP é protegido por reCAPTCHA, que só um navegador real resolve. Por isso, **apenas o login** é feito pelo Edge, numa janela posicionada fora da tela que fecha sozinha em poucos segundos. Isso só acontece quando a sessão expira.
- Com a sessão aberta, o boletim e as páginas de "Detalhar" são lidos por requisições HTTP diretas, sem navegador (cerca de 2 segundos por verificação).
- As notas lidas são comparadas com as da verificação anterior. As disciplinas são identificadas pelo número do diário e as avaliações pela etapa e sigla, então novas linhas no boletim não confundem a comparação.

A API do SUAP do IFSP não foi usada porque, para estudantes, ela não expõe boletim nem notas por avaliação.

## Privacidade

- A senha fica guardada apenas no Gerenciador de Credenciais do Windows.
- O boletim, os cookies de sessão e o log ficam apenas em `%LOCALAPPDATA%\suap-notifier`.
- Nenhum dado é enviado a outro lugar além do próprio SUAP.

## Comandos úteis

Rode a partir de `%LOCALAPPDATA%\suap-notifier\venv\Scripts\python.exe`:

| Comando | O que faz |
|---|---|
| `python -m suap_notifier run` | Verifica agora (é o que a tarefa agendada executa) |
| `python -m suap_notifier run --dry-run` | Mostra o boletim lido, sem salvar nem notificar |
| `python -m suap_notifier setup` | Troca prontuário/senha (ex.: depois de mudar a senha no SUAP) |
| `python -m suap_notifier login` | Abre o Edge para você entrar manualmente, caso o login automático seja barrado pelo reCAPTCHA |
| `python -m suap_notifier test-notification` | Mostra uma notificação de teste |

## Atualizar e desinstalar

```powershell
git pull
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -SkipSetup   # atualizar
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -Uninstall   # remover tarefa, senha e dados
```

## Solução de problemas

- **Nenhuma notificação aparece:** rode `test-notification`. Se nada aparecer, verifique se as notificações do Windows estão ativadas e se o modo "Não incomodar" está desligado.
- **"Login no SUAP falhou":** a senha salva foi recusada. Rode `setup` novamente.
- **"Não foi possível entrar no SUAP automaticamente":** o reCAPTCHA barrou o login automático. Rode `login` e entre pela janela do Edge.
- **Detalhes:** veja o log em `%LOCALAPPDATA%\suap-notifier\notifier.log`.

## Desenvolvimento

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Os testes usam páginas do SUAP anonimizadas em `tests/fixtures/`.
