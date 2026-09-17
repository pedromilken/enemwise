# Instala o pipeline do ENEMWise no Windows (PowerShell 5.1 ou 7).
# Uso, dentro da pasta pipeline:
#   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
#
# Por que escolher a versão do Python: numpy, pandas, scipy e pyarrow só têm pacotes
# prontos (wheels) para versões estáveis. Numa versão alfa, como 3.15.0a3, o pip tenta
# compilar do código-fonte e exige o Visual Studio. O script evita isso.

$ErrorActionPreference = "Continue"   # erros de programas externos são checados por código de saída

function Falhar([string]$msg) {
    Write-Host ""
    Write-Host $msg -ForegroundColor Red
    exit 1
}

if ($PWD.Path -like "*\Windows\System32*") { Falhar "Você está em System32. Entre na pasta 'pipeline' do projeto." }
if (-not (Test-Path ".\pyproject.toml")) { Falhar "pyproject.toml não encontrado. Entre na pasta 'pipeline' antes de rodar." }

# versão estável entre 3.10 e 3.14
$teste = "import sys; v=sys.version_info; ok=(3,10)<=v[:2]<=(3,14) and v.releaselevel=='final'; print(sys.version.split()[0]); sys.exit(0 if ok else 1)"

$pyExe = $null
$pyArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($v in @("3.13", "3.12", "3.14", "3.11", "3.10")) {
        $ver = & py "-$v" -c $teste 2>$null
        if ($LASTEXITCODE -eq 0) { $pyExe = "py"; $pyArgs = @("-$v"); break }
    }
}
if (-not $pyExe) {
    foreach ($cand in @("python", "python3")) {
        if (Get-Command $cand -ErrorAction SilentlyContinue) {
            $ver = & $cand -c $teste 2>$null
            if ($LASTEXITCODE -eq 0) { $pyExe = $cand; break }
        }
    }
}
if (-not $pyExe) {
    Write-Host "Versões de Python encontradas:" -ForegroundColor Yellow
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -0p }
    Falhar ("Nenhuma versão estável entre 3.10 e 3.14. Instale a 3.13 e abra um novo PowerShell:`n" +
            "  winget install --id Python.Python.3.13 -e`n" +
            "ou baixe em https://www.python.org/downloads/ (marque 'Add python.exe to PATH').")
}
Write-Host "Usando Python $ver ($pyExe $($pyArgs -join ' '))" -ForegroundColor Green

function Venv-Python {
    if (Test-Path ".\.venv\Scripts\python.exe") { return ".\.venv\Scripts\python.exe" }
    if (Test-Path "./.venv/bin/python") { return "./.venv/bin/python" }
    return $null
}

# ambiente antigo criado com versão inadequada é recriado
$vpy = Venv-Python
if ($vpy) {
    & $vpy -c $teste 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Removendo .venv criado com uma versão de Python inadequada..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force .\.venv
        $vpy = $null
    }
}
if (-not $vpy) {
    & $pyExe @pyArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Falhar "Não consegui criar o ambiente virtual (.venv)." }
    $vpy = Venv-Python
}

& $vpy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Falhar "Falha ao atualizar o pip." }

# --only-binary: se não houver pacote pronto, falha na hora em vez de tentar compilar
& $vpy -m pip install --only-binary "numpy,pandas,scipy,pyarrow" -e ".[dev,parquet]"
if ($LASTEXITCODE -ne 0) { Falhar "Falha ao instalar as dependências. Cole a mensagem acima na conversa." }

& $vpy -m pytest -q
if ($LASTEXITCODE -ne 0) { Falhar "Instalou, mas algum teste falhou. Cole a saída acima na conversa." }

Write-Host ""
Write-Host "Pronto. Instalação concluída e testes passando." -ForegroundColor Green
Write-Host "Para usar em uma nova janela do PowerShell:"
Write-Host "  cd $($PWD.Path)"
Write-Host "  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  enemwise --help"
