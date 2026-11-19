param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Command
)

$workspace = (Get-Location).Path
docker run --rm --gpus all `
    -v "${workspace}:/workspace" `
    -w /workspace `
    -e MUJOCO_GL=egl `
    -e PYOPENGL_PLATFORM=egl `
    hamster-train:cu128 `
    bash -lc $Command
