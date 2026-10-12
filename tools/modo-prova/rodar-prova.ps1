<#
  Modo prova: agentes fazem a 1ª etapa do ENEM (2009-2025) com o relógio, os dias, as áreas e os cadernos reais de cada ano.

  Uso (na pasta do repositório ENEMWise):
    powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Microdados "D:\microdados" -Etapa preparar
    powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa piloto
    powershell -ExecutionPolicy Bypass -File tools\modo-prova\rodar-prova.ps1 -Etapa completo -Cerebros "qwen3:8b" -Apis "deepseek:deepseek-flash"

  Etapas
    preparar : 1) texto das questões a partir dos PDFs do INEP (pasta provas-inep)
               2) figuras, fórmulas e alternativas em imagem com um modelo de visão local (Ollama, retomável)
               3) cadernos de todas as cores a partir do ITENS_PROVA (precisa de -Microdados)
    piloto   : 3 candidatos por edição, 2 edições (2009 e 2023), para ver tempo e custo
    completo : -Agentes candidatos por edição, 2009-2025, em cada cérebro; depois a análise por área e o KT
    analisar : só refaz ANALISE.md e KT.md das rodadas (ex.: depois de gerar dados\acerto_real.csv)
    nulo     : candidatos sintéticos pela TRI do INEP (sem ordem) e com efeito de posição conhecido: o nulo e o teste de poder
    real     : acerto dos candidatos reais por item e posição (-LongoConfig pipeline\v92.json, ou -Microdados para CN/CH/MT)
    tabela   : Tabela 1 (agentes\saida\TABELA1.md e tabela1.csv) a partir das análises de todas as rodadas
    zenodo   : refaz análises e KT de todas as rodadas completas, a Tabela 1 e monta o pacote em zenodo\
    subir    : envia zenodo\ ao Zenodo como RASCUNHO (pede o token; -Sandbox para testar; -NovaVersaoDe <id> para nova versão)
  -Persona habilidades: cada candidato-agente recebe um perfil de proficiência (condição "LLM com persona")

  Se parar no meio, rode o MESMO comando (mesma -Rodada): o que já foi feito é retomado do disco.
#>
param(
  [ValidateSet("preparar", "piloto", "completo", "analisar", "nulo", "real", "tabela", "zenodo", "subir")][string]$Etapa = "piloto",
  [string]$Provas = "",                 # pasta com <ano>\D1_prova.pdf ... (padrão: provas-inep na raiz do repositório)
  [string]$Microdados = "",             # pasta com ITENS_PROVA_<ano>.csv (os microdados do INEP extraídos)
  [string]$Visao = "qwen2.5vl:7b",      # modelo de visão local para figuras e fórmulas
  [string]$Cerebros = "qwen3:8b",       # cérebros locais (Ollama), separados por vírgula; "nenhum" para só API
  [string]$Apis = "",                   # ex.: "deepseek:deepseek-flash" (memória completa do dia; precisa de $env:DEEPSEEK_API_KEY)
  [int]$Agentes = 20,
  [string]$Anos = "2009-2025",
  [string]$Memoria = "auto",            # auto = janela:6 nos locais, completa nas APIs
  [ValidateSet("chute", "branco")][string]$Esgotado = "chute",
  [ValidateSet("nenhuma", "habilidades")][string]$Persona = "nenhuma",   # habilidades = cada candidato com um perfil (θ e habilidades dominadas)
  [string]$LongoConfig = "",            # etapa real: mapeamento da exportação longa v9.2 (ex.: pipeline\v92.json)
  [string]$Rodada = "",
  [switch]$Sandbox,
  [string]$NovaVersaoDe = ""
)
$ErrorActionPreference = "Stop"
if ($Cerebros -in @("nenhum", "-", "none")) { $Cerebros = "" }
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$aqui = "tools\modo-prova"
if ($Provas -eq "") { $Provas = Join-Path $repo "provas-inep" }
if ($Rodada -eq "") { $Rodada = "$Etapa-" + (Get-Date -Format "yyyy-MM-dd") }
$py = if (Test-Path "pipeline\.venv\Scripts\python.exe") { "pipeline\.venv\Scripts\python.exe" } else { "python" }
New-Item -ItemType Directory -Force -Path "dados" | Out-Null

function Passo([string]$t) { Write-Host ""; Write-Host "== $t" -ForegroundColor Cyan }
function Checar([string]$o) { if ($LASTEXITCODE -ne 0) { Write-Host "Falhou: $o" -ForegroundColor Red; exit 1 } }

if ($Etapa -eq "preparar") {
  Passo "Dependências (PyMuPDF e fontTools)"
  & $py -m pip install --quiet pymupdf fonttools; Checar "pip install"

  Passo "1/3 Texto das questões (PDFs do INEP)"
  if (-not (Test-Path "$Provas\2009\D1_prova.pdf")) { Write-Host "Não achei $Provas\2009\D1_prova.pdf. Baixe com baixar-provas-enem.ps1 ou informe -Provas." -ForegroundColor Red; exit 1 }
  if ((Test-Path "dados\provas-inep.jsonl") -and (Test-Path "dados\recortes")) { Write-Host "dados\provas-inep.jsonl e dados\recortes já existem (apague para refazer)." }
  else { & $py "$aqui\preparar_textos.py" --provas $Provas --saida dados --recortes "dados\recortes"; Checar "preparar_textos" }

  Passo "2/3 Figuras e fórmulas com visão local ($Visao)"
  $ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
  if (-not (Test-Path $ollama)) { $c = Get-Command ollama -ErrorAction SilentlyContinue; if ($c) { $ollama = $c.Source } else { Write-Host "Ollama não encontrado (winget install Ollama.Ollama)." -ForegroundColor Red; exit 1 } }
  & $ollama pull $Visao; Checar "ollama pull $Visao"
  & $py "$aqui\descrever_figuras.py" --dados dados --recortes "dados\recortes" --modelo $Visao; Checar "descrever_figuras"

  Passo "3/3 Cadernos de todas as cores (ITENS_PROVA)"
  if ($Microdados -eq "") { Write-Host "Informe -Microdados com a pasta dos microdados do INEP (onde estão os ITENS_PROVA_<ano>.csv)." -ForegroundColor Red; exit 1 }
  $env:PYTHONPATH = (Join-Path $repo "pipeline")
  & $py "$aqui\exportar_cadernos.py" --raiz $Microdados --textos "dados\provas-inep.jsonl" --anos $Anos --saida "dados\cadernos.json"; Checar "exportar_cadernos"
  Write-Host ""; Write-Host "Pronto. Próximo passo: -Etapa piloto" -ForegroundColor Green
  exit 0
}

if ($Etapa -eq "nulo") {
  # categoria 1 da literatura: candidatos gerados pela TRI do INEP, sem ordem nem aprendizagem; e o mesmo com um efeito
  # de posição conhecido (-0,01 logit por posição), para medir se as análises o recuperam
  foreach ($e in @("0", "-0.01")) {
    $dir = if ($e -eq "0") { "agentes\saida\prova-nulo-tri" } else { "agentes\saida\prova-nulo-tri-efeito" }
    Passo "Nulo TRI (efeito de posição $e)"
    & $py "$aqui\simular_nulo_tri.py" --cadernos dados\cadernos.json --saida $dir --candidatos $Agentes --anos $Anos --efeito-posicao $e; Checar "simular_nulo_tri"
    node "$aqui\modo-prova.js" --consolidar --saida $dir; Checar "consolidar"
    & $py "$aqui\analisar_prova.py" $dir; Checar "analisar_prova"
    & $py "$aqui\kt_prova.py" $dir; Checar "kt_prova"
  }
  exit 0
}
if ($Etapa -eq "real") {
  $env:PYTHONPATH = (Join-Path $repo "pipeline")
  if ($LongoConfig -ne "") { & $py "$aqui\extrair_acerto_real.py" --longo-config $LongoConfig --cadernos dados\cadernos.json --anos $Anos }
  elseif ($Microdados -ne "") { & $py "$aqui\extrair_acerto_real.py" --microdados $Microdados --cadernos dados\cadernos.json --anos $Anos }
  else { Write-Host "Informe -LongoConfig (exportação v9.2; inclui LC) ou -Microdados (só CN, CH e MT)." -ForegroundColor Red; exit 1 }
  Checar "extrair_acerto_real"
  Write-Host "dados\acerto_real.csv pronto: rode -Etapa analisar para incluir a comparação com os candidatos." -ForegroundColor Green
  exit 0
}

if ($Etapa -in @("tabela", "zenodo")) {
  if ($Etapa -eq "zenodo") {
    Get-ChildItem agentes\saida -Directory -Filter "prova-*" | Where-Object { (Test-Path "$($_.FullName)\longo") -and $_.Name -notlike "*piloto*" } | ForEach-Object {
      Passo "Análises: $($_.Name)"
      & $py "$aqui\analisar_prova.py" $_.FullName | Out-Null; Checar "analisar_prova $($_.Name)"
      & $py "$aqui\kt_prova.py" $_.FullName | Out-Null; Checar "kt_prova $($_.Name)"
      & $py "$aqui\kt_prova.py" $_.FullName --so-resolvidas | Out-Null; Checar "kt_prova (só resolvidas) $($_.Name)"
    }
  }
  Passo "Tabela 1"
  & $py "$aqui\tabela1.py" --rodada $(if ($Rodada -ne "") { $Rodada } else { "completo-v13" }); Checar "tabela1"
  if ($Etapa -eq "zenodo") { Passo "Pacote do Zenodo"; & $py "$aqui\pacote_zenodo.py"; Checar "pacote_zenodo" }
  exit 0
}
if ($Etapa -eq "subir") {
  & $py -m pip install --quiet requests; Checar "pip install requests"
  if (-not $env:ZENODO_TOKEN) {
    $s = Read-Host "Token do Zenodo$(if ($Sandbox) { ' (sandbox)' }) (não aparece na tela)" -AsSecureString
    $env:ZENODO_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
  }
  $arg = @(); if ($Sandbox) { $arg += "--sandbox" }; if ($NovaVersaoDe -ne "") { $arg += @("--nova-versao-de", $NovaVersaoDe) }
  & $py "$aqui\subir_zenodo.py" @arg; Checar "subir_zenodo"
  exit 0
}

if (-not (Test-Path "dados\cadernos.json")) { Write-Host "Falta dados\cadernos.json: rode antes -Etapa preparar -Microdados <pasta>." -ForegroundColor Red; exit 1 }
$lista = @()
if ($Cerebros -ne "") { $lista += ($Cerebros.Split(",") | ForEach-Object { "ollama:" + $_.Trim() }) }
if ($Apis -ne "") { $lista += ($Apis.Split(",") | ForEach-Object { $_.Trim() }) }
if ($Etapa -eq "piloto") { $Agentes = 3; $Anos = "2009,2023" }

$pastas = @()
foreach ($c in $lista) {
  $slug = ($c -replace '[^\w.-]+', '_')
  $dir = "agentes\saida\prova-$slug-$Rodada"
  $pastas += $dir
  if ($Etapa -ne "analisar") {
    Passo "Prova: $c ($Agentes candidatos por edição, $Anos)"
    $par = if ($c -like "ollama:*") { 1 } else { 8 }
    if ($c -like "ollama:*") { $env:LAB_NUM_CTX = "16384" }
    if ($c -like "deepseek:*" -and -not $env:DEEPSEEK_API_KEY) {
      $s = Read-Host "Chave da DeepSeek (não aparece na tela)" -AsSecureString
      $env:DEEPSEEK_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
    }
    node "$aqui\modo-prova.js" --cerebro $c --agentes $Agentes --anos $Anos --memoria $Memoria --esgotado $Esgotado --persona $Persona --paralelo $par --saida $dir --rodada $Rodada
    Checar "modo-prova $c"
  }
  Passo "Análise por área: $c"
  & $py "$aqui\analisar_prova.py" $dir; Checar "analisar_prova"
  Passo "KT nas provas: $c"
  & $py "$aqui\kt_prova.py" $dir; Checar "kt_prova"
  & $py "$aqui\kt_prova.py" $dir --so-resolvidas; Checar "kt_prova (só resolvidas)"
}
Write-Host ""; Write-Host "Resultados:" -ForegroundColor Green
$pastas | ForEach-Object { Write-Host "  $_\RESUMO.md, $_\ANALISE.md, $_\KT.md e $_\KT-resolvidas.md" }
