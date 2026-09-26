@echo off
rem ==========================================================================
rem  Instala a segmentação com IA (FastSAM + SAM 2.1). OPCIONAL, cerca de 1 GB.
rem  Depois disso, as fotos de grãos passam a ser segmentadas pela IA: qualquer
rem  fundo, grãos encostados, contornos precisos. Sem ela, a plataforma continua
rem  usando o motor clássico (grãos sobre fundo azul).
rem  Por que estes modelos: docs\decisoes\0009-modelo-de-segmentacao.md
rem ==========================================================================
setlocal
chcp 65001 >nul
title BeanLab - Instalar IA
cd /d "%~dp0"

echo.
echo   BeanLab Coffee Vision - instalar a segmentação com IA
echo   -----------------------------------------------------
if not exist ".venv\Scripts\python.exe" goto sem_plataforma

echo   [1/3] Instalando as bibliotecas de IA (cerca de 1 GB; pode levar 10 minutos)...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements-ia.txt
if errorlevel 1 goto erro
rem O Ultralytics vai sem dependências: ele pediria outro OpenCV, que brigaria com o da plataforma.
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --no-deps -r requirements-ia-ultralytics.txt
if errorlevel 1 goto erro

echo   [2/3] Baixando os modelos (cerca de 180 MB)...
".venv\Scripts\flask.exe" --app app baixar-modelos
if errorlevel 1 goto erro

echo   [3/3] Testando (leva uns 30 segundos)...
".venv\Scripts\flask.exe" --app app verificar-ia
if errorlevel 1 goto erro

echo.
echo   Pronto! Feche a janela da plataforma (se estiver aberta) e abra
echo   "Iniciar BeanLab.bat" de novo. A janela vai mostrar: Grãos (IA).
echo   Fotos já enviadas: na página da coleta, use "Segmentar de novo" em cada foto.
pause
exit /b 0

:sem_plataforma
echo.
echo   Abra primeiro o "Iniciar BeanLab.bat" uma vez (ele prepara o ambiente).
pause
exit /b 1

:erro
echo.
echo   Não deu certo. Confira a conexão com a internet e tente de novo.
echo   Se continuar, copie a mensagem acima e envie ao responsável.
pause
exit /b 1
