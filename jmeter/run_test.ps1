param(
    [string]$Target = "api",
    [int]$Users = 20,
    [int]$Duration = 300,
    [string]$Model = "deepseek-r1:1.5b",
    [double]$Budget = 1.0
)

function Write-ColorOutput {
    param([string]$Text, [string]$Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
# 使用绝对路径避免相对路径问题
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Join-Path $ScriptDir ".."
$ResultsDir = Join-Path $ProjectRoot "results"
$JtlDir = Join-Path $ResultsDir "jtl"
$ReportDir = Join-Path $ResultsDir "reports\$Timestamp"
$SummaryDir = Join-Path $ResultsDir "summary"

New-Item -ItemType Directory -Path $JtlDir -Force | Out-Null
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
New-Item -ItemType Directory -Path $SummaryDir -Force | Out-Null

Write-ColorOutput "========================================" "Blue"
Write-ColorOutput "LLM Performance Test Started" "Green"
Write-ColorOutput "========================================" "Blue"
Write-ColorOutput "Target:   $Target"
Write-ColorOutput "Users:    $Users"
Write-ColorOutput "Duration: $Duration seconds"
Write-ColorOutput "Model:    $Model"
Write-ColorOutput "Budget:   $$Budget USD"
Write-ColorOutput "Timestamp:$Timestamp"
Write-ColorOutput "========================================" "Blue"

if ($Target -eq "api") {
    $TestPlan = "jmeter\plans\deepseek_api_test.jmx"


    if (-not $env:DEEPSEEK_API_KEY) {
        Write-ColorOutput "Error: DEEPSEEK_API_KEY environment variable not set" "Red"
        exit 1
    }
}
elseif ($Target -eq "ollama") {
    $TestPlan = "jmeter\plans\ollama_test.jmx"
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -ErrorAction Stop
    }
    catch {
        Write-ColorOutput "Error: Ollama service not running" "Red"
        exit 1
    }
}
else {
    Write-ColorOutput "Error: Unknown target $Target" "Red"
    exit 1
}

$JtlFile = "$JtlDir\${Target}-${Users}u-${Duration}s-${Timestamp}.jtl"

Write-ColorOutput "Starting test execution..." "Yellow"

$jmeterArgs = @(
    "-n",
    "-t", $TestPlan,
    "-Jusers=$Users",
    "-Jduration=$Duration", 
    "-Jmodel=$Model",
    "-Jbudget=$Budget",
    "-Jjmeter.save.saveservice.output_format=csv",
    "-Jjmeter.save.saveservice.response_data=true",
    "-Jjmeter.save.saveservice.samplerData=true",
    "-Jjmeter.save.saveservice.requestHeaders=true",
    "-Jjmeter.save.saveservice.url=true",
    "-Jjmeter.save.saveservice.assertion_results_failure_message=true",
    "-l", $JtlFile,
    "-e", "-o", $ReportDir
)

# 检查JMeter是否可用
$jmeterCmd = "jmeter"
if (!(Get-Command $jmeterCmd -ErrorAction SilentlyContinue)) {
    # 尝试常见的JMeter安装路径
    $possiblePaths = @(
        "C:\apache-jmeter-*\bin\jmeter.bat",
        "C:\Program Files\Apache\JMeter\bin\jmeter.bat",
        "C:\Program Files (x86)\Apache\JMeter\bin\jmeter.bat",
        "D:\ComputerDownload\Jmeter\*\*\bin\jmeter.bat"
    )
    
    $found = $false
    foreach ($pathPattern in $possiblePaths) {
        $matchingPaths = Get-ChildItem -Path ([System.IO.Path]::GetDirectoryName($pathPattern)) -Filter ([System.IO.Path]::GetFileName($pathPattern)) -Recurse -ErrorAction SilentlyContinue
        if ($matchingPaths) {
            $jmeterCmd = $matchingPaths[0].FullName
            $found = $true
            break
        }
    }
    
    if (!$found) {
        Write-ColorOutput "Error: JMeter not found. Please install JMeter and add it to PATH" "Red"
        Write-ColorOutput "You can install it using: choco install jmeter" "Yellow"
        exit 1
    }
}

& $jmeterCmd @jmeterArgs

if ($LASTEXITCODE -eq 0) {
    Write-ColorOutput "Test completed successfully" "Green"
    Write-ColorOutput "JTL file: $JtlFile"
    Write-ColorOutput "Report:   $ReportDir\index.html"
}
else {
    Write-ColorOutput "Test failed" "Red"
    exit 1
}

Write-ColorOutput "Starting result analysis..." "Yellow"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AnalysisScript = Join-Path $ScriptDir "..\scripts\analyze_results.py"
$pythonArgs = @(
    $AnalysisScript,
    "--jtl", $JtlFile,
    "--target", $Target,
    "--users", $Users,
    "--duration", $Duration,
    "--budget", $Budget,
    "--output", $SummaryDir
)

& python @pythonArgs

$analysisResult = $LASTEXITCODE
if ($analysisResult -eq 2) {
    Write-ColorOutput "Budget exceeded! Pipeline should fail" "Red"
    exit 1
}
elseif ($analysisResult -eq 0) {
    Write-ColorOutput "Budget within limits" "Green"
}
else {
    Write-ColorOutput "Analysis failed" "Red"
    exit 1
}

Write-ColorOutput "All steps completed" "Green"