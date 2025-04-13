sphnix\make.bat html
if (Test-Path docs -PathType Container) {
	Remove-Item -Force -Recurse docs
}
Copy-Item -Recurse sphnix/build/html docs
pause