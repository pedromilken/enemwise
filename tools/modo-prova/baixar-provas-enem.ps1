<#
  Baixa do INEP o caderno AMARELO de cada dia (prova + gabarito), 2009 a 2025, para o modo prova do ENEMWise.
  Uma cor por dia basta: a ordem das outras cores vem do ITENS_PROVA (CO_POSICAO por CO_PROVA).
  Uso (na pasta do enemwise):  powershell -ExecutionPolicy Bypass -File tools\modo-prova\baixar-provas-enem.ps1
  Retomável: o que já foi baixado é pulado. No fim, lista o que falhou para conferir à mão no site do INEP.
#>
$ErrorActionPreference = "Continue"
$dest = Join-Path (Get-Location) "provas-inep"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$E = "https://download.inep.gov.br/educacao_basica/enem"
$N = "https://download.inep.gov.br/enem/provas_e_gabaritos"
$L = @(
 @(2009,"$E/provas/2009/dia1_caderno2_amarelo.pdf","$E/gabaritos/2009/gabarito_dia1.pdf","$E/provas/2009/dia2_caderno5_amarelo.pdf","$E/gabaritos/2009/gabarito_dia2.pdf"),
 @(2010,"$E/provas/2010/dia1_caderno2_amarelo.pdf","$E/provas/2010/dia1_caderno2_amarelo_com_gab.pdf","$E/provas/2010/dia2_caderno5_amarelo.pdf","$E/provas/2010/dia2_caderno5_amarelo_com_gab.pdf"),
 @(2011,"$E/provas/2011/dia1_caderno2_amarelo.pdf","$E/gabaritos/2011/02_AMARELO_GABARITO.pdf","$E/provas/2011/dia2_caderno5_amarelo.pdf","$E/gabaritos/2011/05_AMARELO_GABARITO.pdf"),
 @(2012,"$E/provas/2012/dia1_caderno2_amarelo.pdf","$E/gabaritos/2012/dia1_amarelo.pdf","$E/provas/2012/dia2_caderno5_amarelo.pdf","$E/gabaritos/2012/dia2_amarelo.pdf"),
 @(2013,"$E/provas/2013/dia1_caderno2_amarelo.pdf","$E/gabaritos/2013/dia1_amarelo.pdf","$E/provas/2013/dia2_caderno5_amarelo.pdf","$E/gabaritos/2013/dia2_amarelo.pdf"),
 @(2014,"$E/provas/2014/2014_PV_impresso_D1_CD2.pdf","$E/gabaritos/2014/CADERNO_2_AMARELO_SABADO.pdf","$E/provas/2014/2014_PV_impresso_D2_CD5.pdf","$E/gabaritos/2014/CADERNO_5_AMARELO_DOMINGO.pdf"),
 @(2015,"$E/provas/2015/2015_PV_impresso_D1_CD2.pdf","$E/gabaritos/2015/CADERNO_2_AMARELO_SABADO.pdf","$E/provas/2015/2015_PV_impresso_D2_CD5.pdf","$E/gabaritos/2015/CADERNO_5_AMARELO_DOMINGO.pdf"),
 @(2016,"$E/provas/2016/2016_PV_impresso_D1_CD2.pdf","$E/gabaritos/2016/GAB_ENEM_2016_DIA_1_02_AMARELO.pdf","$E/provas/2016/2016_PV_impresso_D2_CD5.pdf","$E/gabaritos/2016/GAB_ENEM_2016_DIA_2_05_AMARELO.pdf"),
 @(2017,"$E/provas/2017/cad_2_prova_amarelo_5112017.pdf","$E/gabaritos/2017/cad_2_gabarito_amarelo_5112017.pdf","$E/provas/2017/2017_PV_impresso_D2_CD5.pdf","$E/gabaritos/2017/cad_5_gabarito_amarelo_12112017.pdf"),
 @(2018,"$E/provas/2018/2018_PV_impresso_D1_CD2.pdf","$E/gabaritos/2018/GAB_ENEM_2018_DIA_1_AMARELO.pdf","$E/provas/2018/2DIA_05_AMARELO_BAIXA.pdf","$E/gabaritos/2018/GAB_ENEM_2018_DIA_2_AMARELO.pdf"),
 @(2019,"$E/provas/2019/2019_PV_impresso_D1_CD2.pdf","$E/gabaritos/2019/gabarito_1_dia_caderno_2_amarelo_aplicacao_regular.pdf","$E/provas/2019/2019_PV_impresso_D2_CD5.pdf","$E/gabaritos/2019/gabarito_2_dia_caderno_5_amarelo_aplicacao_regular.pdf")
)
foreach ($a in 2020..2025) { $L += ,@($a,"$N/${a}_PV_impresso_D1_CD2.pdf","$N/${a}_GB_impresso_D1_CD2.pdf","$N/${a}_PV_impresso_D2_CD5.pdf","$N/${a}_GB_impresso_D2_CD5.pdf") }
$falhas = @()
foreach ($x in $L) {
  $ano = $x[0]; $d = Join-Path $dest $ano; New-Item -ItemType Directory -Force -Path $d | Out-Null
  $nomes = @("D1_prova.pdf","D1_gabarito.pdf","D2_prova.pdf","D2_gabarito.pdf")
  for ($i = 0; $i -lt 4; $i++) {
    $f = Join-Path $d $nomes[$i]; $u = $x[$i + 1]
    if ((Test-Path $f) -and ((Get-Item $f).Length -gt 20000)) { continue }
    try { Invoke-WebRequest -Uri $u -OutFile $f -UseBasicParsing -TimeoutSec 180; Write-Host "ok  $ano $($nomes[$i])" }
    catch { Write-Host "FALHOU $ano $($nomes[$i])  $u" -ForegroundColor Yellow; $falhas += "$ano $($nomes[$i]) $u"; Remove-Item $f -ErrorAction SilentlyContinue }
  }
}
Write-Host "`nPronto em $dest" -ForegroundColor Green
if ($falhas.Count) { Write-Host "Falharam (baixe à mão no site do INEP, caderno AMARELO, e salve com o mesmo nome):" -ForegroundColor Yellow; $falhas | ForEach-Object { Write-Host "  $_" } }
