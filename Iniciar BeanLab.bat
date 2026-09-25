@echo off
rem ==========================================================================
rem  Inicia a plataforma BeanLab Coffee Vision com dois cliques.
rem  1. Cria o ambiente virtual (.venv) com Python 3.14, se ainda não existir.
rem  2. Instala as dependências, mas só quando o requirements.txt mudar.
rem  3. Inicia o servidor e abre o navegador.
rem ==========================================================================
setlocal
chcp 65001 >nul
title BeanLab Coffee Vision
cd /d "%~dp0"

echo.
echo   BeanLab Coffee Vision
echo   ---------------------

rem --- 1. Ambiente virtual -------------------------------------------------
if exist ".venv\Scripts\python.exe" goto dependencias
echo   [1/3] Preparando o ambiente (só na primeira vez, pode levar alguns minutos)...
rem As versões das bibliotecas em requirements.txt foram testadas com Python 3.14.
py -3.14 -m venv .venv
if errorlevel 1 goto sem_python

:dependencias
rem --- 2. Dependências (compara com a cópia salva da última instalação) ----
set "REQ_INSTALADO=.venv\requirements.instalado.txt"
fc /b requirements.txt "%REQ_INSTALADO%" >nul 2>&1
if not errorlevel 1 goto iniciar
echo   [2/3] Instalando dependências...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto erro_pip
copy /y requirements.txt "%REQ_INSTALADO%" >nul

:iniciar
rem --- 3. Servidor ---------------------------------------------------------
echo   [3/3] Iniciando o servidor...
if not defined CAFE_ABRIR_NAVEGADOR set "CAFE_ABRIR_NAVEGADOR=1"
".venv\Scripts\python.exe" run.py
echo.
echo   O servidor parou. Se apareceu um erro acima, copie a mensagem e envie ao responsável.
pause
exit /b

:sem_python
echo.
echo   ERRO: o Python 3.14 não foi encontrado neste computador.
echo   Instale em: https://www.python.org/downloads/
echo   (na instalação, marque "Add python.exe to PATH") e tente de novo.
pause
exit /b 1

:erro_pip
echo.
echo   ERRO ao instalar as dependências. Verifique a conexão com a internet e tente de novo.
pause
exit /b 1
