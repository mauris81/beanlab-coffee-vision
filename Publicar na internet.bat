@echo off
rem ==========================================================================
rem  Liga ou desliga a plataforma na internet (Tailscale Funnel).
rem  Ligada, os celulares entram de qualquer lugar (dados móveis, outro Wi-Fi)
rem  pelo endereço https://<nome-deste-pc>.<sua-rede>.ts.net, com cadeado.
rem  A plataforma continua rodando NESTE PC: ele precisa ficar ligado, com a
rem  janela do "Iniciar BeanLab.bat" aberta. Guia completo: docs\PUBLICACAO.md
rem ==========================================================================
setlocal
chcp 65001 >nul
title BeanLab - Publicar na internet
cd /d "%~dp0"

set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
if exist "%TS%" goto menu
set "TS=tailscale"
where tailscale >nul 2>&1
if errorlevel 1 goto sem_tailscale

:menu
if not defined CAFE_PORT set "CAFE_PORT=5000"
echo.
echo   BeanLab Coffee Vision - publicar na internet
echo   --------------------------------------------
echo.
echo   Situação agora ("No serve config" = desligada):
echo.
"%TS%" funnel status
echo.
echo   [1] Publicar: ligar o endereço na internet
echo   [2] Tirar da internet: desligar o endereço
echo   [3] Sair sem mudar nada
echo.
choice /c 123 /n /m "  Escolha 1, 2 ou 3: "
if errorlevel 3 exit /b 0
if errorlevel 2 goto desligar

:ligar
echo.
echo   Ligando... Na primeira vez aparece um link: abra no navegador, entre na
echo   sua conta do Tailscale e aprove. Depois disso esta janela continua sozinha.
echo.
"%TS%" funnel --bg %CAFE_PORT%
if errorlevel 1 goto erro
echo.
echo   Pronto! O endereço com https:// acima é o da plataforma na internet.
echo   Mande para a equipe. Ele também aparece na janela do "Iniciar BeanLab.bat"
echo   (feche e abra a plataforma de novo para ver).
echo.
echo   Lembre: a plataforma precisa estar aberta e este PC ligado.
pause
exit /b 0

:desligar
"%TS%" funnel --https=443 off
if errorlevel 1 goto erro
echo.
echo   Pronto: a plataforma saiu da internet. No Wi-Fi daqui continua funcionando.
pause
exit /b 0

:sem_tailscale
echo.
echo   O Tailscale não está instalado neste PC.
echo   Instale em https://tailscale.com/download e entre com a sua conta.
pause
exit /b 1

:erro
echo.
echo   Não deu certo. Confira se o Tailscale está aberto e conectado (ícone perto do
echo   relógio) e tente de novo. Se continuar, copie a mensagem acima e envie ao responsável.
pause
exit /b 1
