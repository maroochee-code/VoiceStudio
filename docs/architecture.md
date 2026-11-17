# VoiceStudio 구성도

## 1. 전체 구조

```mermaid
flowchart TB
    User([사용자 · 브라우저<br/>127.0.0.1:7860])
    Mic[[K66 마이크]]
    Spk[[스피커]]

    subgraph Main["메인 프로그램 (.venv · Python 3.10 · PyTorch 2.5.1)"]
        UI["웹 화면 app/ui.py<br/>녹음 · 말→글자 · 글자→말 · 음성 대화<br/>목소리 학습 · 목소리 관리 · 엔진 상태"]
        EM{{"엔진 관리자 (지휘자)<br/>app/engine_manager.py<br/>GPU엔 한 번에 하나만"}}
        REC["녹음 app/recorder.py"]
        STT["위스퍼 app/stt.py<br/>GPU ↔ CPU 자동 전환"]
        TTS["멜로 app/tts.py<br/>항상 CPU"]
        VO["목소리 목록 app/voices.py<br/>기본 / 학습 / 샘플 · 라이선스 · MP3"]
        SV["GPT-SoVITS 연결 app/sovits.py<br/>학습 지휘 · 합성 서버 켜기/끄기"]
        LLM["Ollama 연결 app/llm.py<br/>답변 후 keep_alive=0"]
    end

    subgraph SovitsEnv["GPT-SoVITS (별도 .venv · PyTorch 2.6)"]
        TRAIN["학습 스크립트<br/>자르기 · 특징 추출 · SoVITS/GPT 학습"]
        API["합성 서버 api_v2<br/>127.0.0.1:9880"]
    end

    OLL["Ollama 서버<br/>127.0.0.1:11434<br/>gemma3:4b"]

    subgraph Disk["D: 저장소"]
        DATA[("data/<br/>recordings · samples · outputs<br/>voices/trained · voices/samples")]
        MODELS[("models/<br/>whisper · huggingface · nltk_data")]
        OMOD[("D:/LocalAI/AImodels<br/>Ollama 모델")]
    end

    User <--> UI
    Mic --> REC
    UI --> EM
    EM --> STT & TTS & SV & LLM
    UI --> REC & VO
    SV -->|하위 프로세스| TRAIN
    SV -->|HTTP| API
    LLM -->|HTTP| OLL
    REC & STT & TTS & SV & VO --> DATA
    STT & TTS --> MODELS
    OLL --> OMOD
    UI --> Spk
```

## 2. 음성 대화 한 번의 흐름

```mermaid
sequenceDiagram
    participant U as 사용자
    participant UI as 웹 화면
    participant EM as 엔진 관리자
    participant W as 위스퍼 (CPU)
    participant O as Ollama (GPU)
    participant V as 목소리 (멜로 CPU / SoVITS GPU)

    U->>UI: 말하기 (녹음 끝)
    UI->>W: 받아쓰기
    W-->>UI: 질문 글자
    UI->>EM: Ollama 켜기 요청
    EM->>EM: GPU에 있는 다른 엔진 내리기
    UI->>O: 질문 + 대화 기록 (keep_alive=0)
    O-->>UI: 답변 (끝나면 바로 GPU에서 내려감)
    alt 학습·샘플 목소리
        UI->>EM: SoVITS 켜기 요청 (GPU 정리 후)
    end
    UI->>V: 답변 읽기
    V-->>U: 답변 음성 자동 재생
```

## 3. 목소리 학습 흐름

```mermaid
flowchart LR
    A[녹음 탭<br/>샘플 보내기<br/>합계 60초 이상] --> B[1 자르기<br/>문장 단위]
    B --> C[2 받아쓰기<br/>위스퍼]
    C --> D[GPU 비우기<br/>위스퍼·Ollama 내림]
    D --> E[3 특징 추출<br/>발음·음색·화자·의미]
    E --> F[4 SoVITS 학습<br/>음색]
    F --> G[5 GPT 학습<br/>말투]
    G --> H[6 저장<br/>data/voices/trained]
```

## 4. GPU(VRAM 6GB) 사용 규칙

| 엔진 | 위치 | 대략 VRAM | 언제 올라가나 |
|---|---|---|---|
| 위스퍼 small | GPU(여유 없으면 CPU) / 음성 대화 중엔 CPU | 약 1GB | 말→글자 변환 |
| 멜로 | 항상 CPU | 0 | 글자→말(기본 목소리) |
| GPT-SoVITS 합성 서버 | GPU | 약 2~3GB | 학습·샘플 목소리로 읽을 때 |
| GPT-SoVITS 학습 | GPU 독점 | 약 4~5GB | 학습 중 (다른 GPU 엔진 금지) |
| Ollama gemma3:4b | GPU | 약 4GB | 답변하는 동안만 |

GPU를 쓰는 엔진을 켜기 전에 엔진 관리자가 다른 GPU 엔진을 먼저 내립니다.
