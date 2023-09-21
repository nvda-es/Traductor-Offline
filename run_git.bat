@cls
@echo off
scons --clean
scons pot
git init
git add --all
git commit -m "Versión 2023.09.21"
git push -u origin master
pause