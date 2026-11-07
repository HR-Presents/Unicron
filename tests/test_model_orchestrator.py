"""Model orchestrator selection tests."""

from backend.app.model_orchestrator.selector import recommend


def hardware(vram=8188, active=None, vllm=True, llama=False):
    return {
        "gpus": (
            [{
                "vram_total_mib": vram,
                "vram_free_mib": vram,
            }]
            if vram else []
        ),
        "runtimes": {
            "vllm": vllm,
            "llama_cpp": llama,
            "ollama": False,
        },
        "inference": {
            "reachable": bool(active),
            "models": active or [],
        },
    }


def by_model(result, name):
    return next(
        candidate
        for candidate in result["candidates"]
        if candidate["model"] == name
    )


def test_reuses_existing_model():
    result = recommend(hardware(active=["unicron-qwen"]))
    assert result["selected"]["status"] == "reuse_active_endpoint"
    assert result["selected"]["model"] == "Qwen/Qwen3-1.7B"


def test_no_gpu_does_not_claim_gpu_fit():
    result = recommend(hardware(vram=0))
    assert result["selected"] is None
    assert by_model(
        result, "Qwen/Qwen3-1.7B"
    )["status"] == "estimated_vram_insufficient"


def test_large_fp16_model_rejected_on_8gb():
    result = recommend(hardware())
    assert by_model(
        result, "Qwen/Qwen3-4B"
    )["status"] == "estimated_vram_insufficient"


def test_missing_runtime_is_detected():
    result = recommend(hardware())
    assert by_model(
        result, "Qwen/Qwen3-8B"
    )["status"] == "runtime_unavailable"


def test_quantized_candidate_requires_validation():
    result = recommend(hardware(llama=True))
    assert by_model(
        result, "Qwen/Qwen3-8B"
    )["status"] == "requires_validation"


def test_unreachable_endpoint_is_not_reused():
    result = recommend(hardware(active=[]))
    assert result["selected"] is None


def test_selector_never_switches_automatically():
    result = recommend(hardware(active=["unicron-qwen"]))
    assert result["automatic_switch_performed"] is False
