#!/usr/bin/env python3
"""
GPU/CUDA Detection and Whisper Device Test
Checks if your system can use GPU acceleration for transcription
"""

import torch
import whisper

def check_gpu_status():
    """Check GPU availability and status"""
    print("🔍 GPU/CUDA Detection Report")
    print("=" * 50)
    
    # Check PyTorch CUDA support
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        print(f"CUDA version: {torch.version.cuda}")
        print(f"GPU device count: {torch.cuda.device_count()}")
        print(f"Current device: {torch.cuda.current_device()}")
        print(f"GPU name: {torch.cuda.get_device_name(0)}")
        print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    else:
        print("❌ No CUDA-capable GPU detected")
        print("💡 To enable GPU acceleration:")
        print("   1. Install CUDA toolkit")
        print("   2. Install PyTorch with CUDA support:")
        print("      pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
    
    print("\n🎯 Whisper Device Test")
    print("=" * 30)
    
    try:
        # Test Whisper device detection
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Whisper will use: {device.upper()}")
        
        # Load a tiny model to test
        print("Loading Whisper model...")
        model = whisper.load_model("tiny", device=device)
        
        # Check actual device
        if hasattr(model, 'encoder'):
            model_device = next(model.encoder.parameters()).device
            print(f"Model loaded on: {model_device}")
        else:
            print("Model loaded successfully")
            
        print("✅ Whisper GPU test completed")
        
    except Exception as e:
        print(f"❌ Whisper test failed: {e}")
    
    print("\n📊 Performance Recommendations")
    print("=" * 35)
    
    if torch.cuda.is_available():
        print("🚀 GPU acceleration is available!")
        print("   - Transcription will be significantly faster")
        print("   - Recommended models: base, small, medium, large")
        print("   - Current setup is optimal")
    else:
        print("⚠️  CPU-only mode detected")
        print("   - Transcription will be slower")
        print("   - Recommended models: tiny, base")
        print("   - Consider installing CUDA for better performance")

if __name__ == "__main__":
    check_gpu_status()
