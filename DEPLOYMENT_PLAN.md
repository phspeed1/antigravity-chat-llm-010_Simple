
# AntiGravity 프로젝트 Google Cloud (GCP) 배포 계획

AWS 대신 **Google Cloud Platform (GCP)**를 사용하여 배포하는 전략입니다. 프로젝트가 3개의 서비스(Frontend, Node.js Backend, Python LLM Service)로 구성되어 있으므로, 관리의 편의성을 위해 **Google Compute Engine (GCE)**를 활용한 Docker Compose 배포 방식을 권장합니다.

## 1. 아키텍처 개요
- **Frontend**: React (Vite) - Nginx 컨테이너로 정적 서빙.
- **Backend**: Node.js (Express) - 인증 및 사용자 관리 API.
- **LLM Service**: Python (FastAPI) - RAG 및 Vision 처리 (메모리 사용량 높음).
- **Database**: Supabase (PostgreSQL), Pinecone (Vector DB) - *GCP 외부 서비스이므로 그대로 유지.*

## 2. GCP 환경 구성 권장 사항

### A. Google Compute Engine (VM)
- **머신 유형**: **e2-standard-2** 권장
  - 사양: 2 vCPU, 8GB 메모리
  - 이유: `py-zerox` 및 PDF 이미지 변환 작업은 메모리를 많이 소모합니다. 4GB 이하(e2-medium)에서는 OOM(Out of Memory) 에러가 발생할 위험이 높습니다.
- **OS**: Ubuntu 22.04 LTS (x86/64)
- **디스크**: Balanced Persistent Disk 30GB 이상

### B. 네트워크 및 보안
1. **고정 IP 주소 (Static External IP)**: 서버 재시작 시 IP가 바뀌지 않도록 예약합니다.
2. **방화벽 규칙 (VPC Firewall)**:
   - `tcp:80`, `tcp:443` (HTTP/HTTPS) 허용.
   - 개발/테스트 목적이라면 `tcp:3000`, `tcp:8000`도 열 수 있으나, Nginx Reverse Proxy를 통해 80/443 포트로 통합하는 것이 보안상 좋습니다.

## 3. 배포 준비 (Local Steps)

### A. 환경 변수 정리
GCP VM에 업로드할 `.env.production` 파일을 준비합니다.
- `JWT_SECRET`: 강력한 난수로 변경.
- `CLIENT_URL`: GCP VM의 고정 IP 또는 연결할 도메인 주소.
- `OPENAI_API_KEY` 등 외부 키 확인.

### B. Docker 구성 (Docker Compose)
Google Cloud VM 하나에 3개의 컨테이너를 효율적으로 띄우기 위해 Docker Compose를 사용합니다.

**docker-compose.yml 예시:**
```yaml
version: '3.8'
services:
  # Nginx Reverse Proxy & Frontend
  web:
    build: ./client
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
      - llm
  
  # Node.js Backend
  api:
    build: ./server
    env_file: ./server/.env
    restart: always

  # Python LLM Service
  llm:
    build: ./llm_service
    env_file: ./llm_service/.env
    # Linux 시스템 패키지(poppler-utils 등) 설치를 위해 Dockerfile 수정 필수
    restart: always
    volumes:
      - ./llm_service/documents:/documents
```

## 4. 상세 배포 절차 (Action Plan)

### 단계 1: GCP VM 인스턴스 생성
1. Google Cloud Console > Compute Engine > VM 인스턴스 만들기.
2. 리전: `asia-northeast3` (서울) 권장.
3. 머신 구성: `e2-standard-2`.
4. 부팅 디스크: Ubuntu 22.04 LTS.
5. 방화벽: 'HTTP 트래픽 허용', 'HTTPS 트래픽 허용' 체크.

### 단계 2: 서버 환경 설정
VM에 SSH로 접속하여 필수 도구를 설치합니다.
```bash
# Docker 및 Docker Compose 설치
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
# (Docker 공식 설치 스크립트 활용 권장)
...
```

### 단계 3: 코드 배포
1. git clone으로 프로젝트를 VM에 내려받습니다.
2. 로컬에서 준비한 `.env` 파일들을 각 디렉토리(`client/`, `server/`, `llm_service/`)에 생성/복사합니다.

### 단계 4: 서비스 실행
```bash
# 백그라운드 실행
sudo docker-compose up -d --build
```

## 5. 중요 고려 사항 (GCP 특화)

- **Cloud Storage (GCS) 연동 고려**: 현재 로컬 파일 시스템을 임시로 사용하고 있으나, PDF 처리 중 생성되는 임시 파일이 많아지면 디스크 용량이 찰 수 있습니다. 주기적으로 정리하는 크론(Cron) 작업이나 GCS를 활용하는 로직 변경을 고려하세요.
- **비용 관리**: `e2-standard-2`는 월 약 $50~60 수준(서울 리전 기준)의 비용이 발생할 수 있습니다. 비용 절감이 중요하다면 **Spot VM (Preemptible)**을 고려할 수 있으나, 서버가 불시에 중단될 수 있습니다.
- **SSL 인증서**: 도메인을 구매하여 연결하고, Nginx 컨테이너 내에서 **Certbot**을 실행하여 Let's Encrypt 무료 인증서를 적용해야 합니다.

## 6. 대안: Cloud Run (Serverless)
서버 관리 없이 배포하려면 **Cloud Run**을 사용할 수 있습니다.
- **장점**: 트래픽이 없을 때 비용 0원, 자동 스케일링.
- **단점**: 
  - 3개의 서비스(Front, Back, LLM)를 각각 따로 배포하고 연동해야 하므로 초기 설정이 복잡함.
  - Python LLM 서비스의 경우 긴 처리 시간(Timeout)과 높은 메모리 설정이 필요하여 설정 튜닝이 까다로울 수 있음.
  - `py-zerox`와 같은 무거운 라이브러리는 컨테이너 콜드 스타트(Cold Start) 시 지연을 유발할 수 있음.

**결론**: 현재 단계에서는 **GCE + Docker Compose** 방식이 가장 빠르고 안정적인 배포 방법입니다.
