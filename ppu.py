import argparse
import time
import multiprocessing as mp
import torch


def occupy_memory(device, ratio=0.8, block_mb=256):
    free, total = torch.cuda.mem_get_info(device)
    target_bytes = int(free * ratio)

    blocks = []
    block_bytes = block_mb * 1024 * 1024
    dtype = torch.float32
    element_size = torch.tensor([], dtype=dtype).element_size()
    elements_per_block = block_bytes // element_size

    allocated = 0

    print(
        f"[GPU {device.index}] Free: {free / 1024**3:.2f} GB, "
        f"target: {target_bytes / 1024**3:.2f} GB",
        flush=True,
    )

    while allocated + block_bytes < target_bytes:
        try:
            x = torch.empty(elements_per_block, device=device, dtype=dtype)
            blocks.append(x)
            allocated += block_bytes
        except RuntimeError as e:
            print(f"[GPU {device.index}] Allocation stopped: {e}", flush=True)
            break

    print(f"[GPU {device.index}] Allocated: {allocated / 1024**3:.2f} GB", flush=True)
    return blocks


def stress_gpu(gpu_id, mem_ratio, block_mb, matrix_size, sleep):
    torch.cuda.set_device(gpu_id)
    device = torch.device(f"cuda:{gpu_id}")

    print(f"[GPU {gpu_id}] Using {torch.cuda.get_device_name(device)}", flush=True)

    memory_blocks = occupy_memory(
        device=device,
        ratio=mem_ratio,
        block_mb=block_mb,
    )

    try:
        a = torch.randn(matrix_size, matrix_size, device=device)
        b = torch.randn(matrix_size, matrix_size, device=device)

        print(f"[GPU {gpu_id}] Compute stress started", flush=True)

        while True:
            c = a @ b
            torch.cuda.synchronize(device)
            _ = c[0, 0].item()

            if sleep > 0:
                time.sleep(sleep)

    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        print(f"[GPU {gpu_id}] Runtime error: {e}", flush=True)
    finally:
        del memory_blocks
        torch.cuda.empty_cache()
        print(f"[GPU {gpu_id}] Released memory", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpus", type=str, default="0,1,2,3,4,5,6,7")
    parser.add_argument("--mem-ratio", type=float, default=0.8)
    parser.add_argument("--block-mb", type=int, default=256)
    parser.add_argument("--matrix-size", type=int, default=8192)
    parser.add_argument("--sleep", type=float, default=0.0)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    gpu_ids = [int(x.strip()) for x in args.gpus.split(",") if x.strip() != ""]

    available = torch.cuda.device_count()
    for gpu_id in gpu_ids:
        if gpu_id >= available:
            raise ValueError(f"GPU {gpu_id} 不存在。当前只有 {available} 张卡。")

    mp.set_start_method("spawn", force=True)

    processes = []
    for gpu_id in gpu_ids:
        p = mp.Process(
            target=stress_gpu,
            args=(
                gpu_id,
                args.mem_ratio,
                args.block_mb,
                args.matrix_size,
                args.sleep,
            ),
        )
        p.start()
        processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\nStopping all GPUs...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join()


if __name__ == "__main__":
    main()