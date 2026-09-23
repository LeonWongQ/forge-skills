param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$PythonExecutableBase64,
    [Parameter(Mandatory = $true, Position = 1)]
    [string]$HookScriptBase64,
    [Parameter(Mandatory = $true)]
    [Alias('host')]
    [string]$HookHost,
    [Parameter(Mandatory = $true)]
    [Alias('event')]
    [string]$HookEvent,
    [Parameter(Mandatory = $true)]
    [Alias('forge-hook-marker')]
    [string]$Marker,
    [Parameter(Mandatory = $true)]
    [Alias('forge-root')]
    [string]$ForgeRoot
)

$PythonExecutable = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($PythonExecutableBase64))
$HookScript = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($HookScriptBase64))
& $PythonExecutable $HookScript --host $HookHost --event $HookEvent --forge-hook-marker $Marker --forge-root $ForgeRoot
exit $LASTEXITCODE
