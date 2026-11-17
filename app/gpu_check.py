"""GPU 인식 확인 스크립트 (1단계).

실행: .venv\\Scripts\\python.exe app\\gpu_check.py
"""
import sys


def get_gpu_info() -> dict:
    """GPU 상태를 사전(dict)으로 돌려준다. GPU가 없으면 available=False."""
    import torch

    info = {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "cuda_build": torch.version.cuda,
        "available": torch.cuda.is_available(),
    }
    if info["available"]:
        props = torch.cuda.get_device_properties(0)
        free, total = torch.cuda.mem_get_info(0)
        info.update(
            name=props.name,
            vram_total_mb=total // (1024 * 1024),
            vram_free_mb=free // (1024 * 1024),
            arch=f"sm_{props.major}{props.minor}",
        )
    return info


def main() -> int:
    try:
        info = get_gpu_info()
    except ImportError:
        print("오류: PyTorch가 설치되어 있지 않습니다. 가상환경(.venv)에서 실행했는지 확인하세요.")
        return 1

    print(f"파이썬 버전   : {info['python']}")
    print(f"PyTorch 버전  : {info['torch']} (CUDA {info['cuda_build']})")
    if not info["available"]:
        print("결과: GPU를 찾지 못했습니다. 그래픽 드라이버를 확인하세요.")
        return 1
    print(f"그래픽카드    : {info['name']} ({info['arch']})")
    print(f"VRAM          : 전체 {info['vram_total_mb']}MB / 남은 용량 {info['vram_free_mb']}MB")
    print("결과: GPU 인식 성공")
    return 0


if __name__ == "__main__":
    sys.exit(main())
