$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
Set-Location $repoRoot

$configs = @(
  "configs/evaluation/model_benchmarks/incremental_qwen35plus_dashscope_siliconflow_gate_test_full.example.json",
  "configs/evaluation/model_benchmarks/incremental_gemini3flash_google_siliconflow_gate_test_full.example.json",
  "configs/evaluation/model_benchmarks/incremental_moonshot_k25_siliconflow_gate_test_full.example.json",
  "configs/evaluation/model_benchmarks/incremental_claude_sonnet45_siliconflow_gate_test_full.example.json",
  "configs/evaluation/model_benchmarks/incremental_gpt54_openrouter_siliconflow_gate_test_full.example.json",
  "configs/evaluation/model_benchmarks/incremental_qwen35plus_dashscope_thinking_on_siliconflow_gate_test_full.example.json"
)

$python = "python"

Write-Output ("[{0}] Incremental full campaign started." -f (Get-Date -Format "s"))
foreach ($config in $configs) {
  Write-Output ("[{0}] START {1}" -f (Get-Date -Format "s"), $config)
  & $python "tools/eval/run_incremental_benchmark.py" "--config" $config
  if ($LASTEXITCODE -ne 0) {
    throw "Benchmark failed for $config with exit code $LASTEXITCODE"
  }
  Write-Output ("[{0}] DONE  {1}" -f (Get-Date -Format "s"), $config)
}
Write-Output ("[{0}] Incremental full campaign finished." -f (Get-Date -Format "s"))
