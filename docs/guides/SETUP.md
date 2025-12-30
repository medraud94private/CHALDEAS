# 개발 환경 설정 가이드

## 필수 요구사항

- Docker & Docker Compose
- Node.js 20+ (로컬 개발용)
- Python 3.12+ (로컬 개발용)
- Git

## 빠른 시작 (Docker)

```bash
# 1. 저장소 클론
git clone <repository-url>
cd Chaldeas

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 필요한 값 수정

# 3. Docker로 실행
docker-compose up -d

# 4. 접속
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API 문서: http://localhost:8000/docs
```

## 로컬 개발 (권장)

### Backend

```bash
cd backend

# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
export DATABASE_URL="postgresql://chaldeas:chaldeas_dev@localhost:5432/chaldeas"

# DB 마이그레이션
alembic upgrade head

# 서버 실행
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

### Database

```bash
# PostgreSQL Docker 컨테이너만 실행
docker-compose up -d db

# 접속 정보
# Host: localhost
# Port: 5432
# User: chaldeas
# Password: chaldeas_dev
# Database: chaldeas
```

## 환경 변수

### .env 파일

```env
# Database
POSTGRES_USER=chaldeas
POSTGRES_PASSWORD=chaldeas_dev
POSTGRES_DB=chaldeas

# Environment
ENVIRONMENT=development

# AI API Keys (선택)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Frontend
VITE_API_URL=http://localhost:8000
```

## 시드 데이터 로드

```bash
cd backend

# 시드 데이터 로드
python -m app.db.seed
```

## 테스트

```bash
# Backend 테스트
cd backend
pytest

# Frontend 테스트
cd frontend
npm test
```

## 트러블슈팅

### Docker 관련

```bash
# 컨테이너 로그 확인
docker-compose logs -f backend
docker-compose logs -f frontend

# 컨테이너 재시작
docker-compose restart backend

# 전체 재빌드
docker-compose down
docker-compose up -d --build
```

### DB 관련

```bash
# DB 초기화
docker-compose down -v  # 볼륨 삭제
docker-compose up -d

# 마이그레이션 재실행
alembic downgrade base
alembic upgrade head
```

### 포트 충돌

```bash
# 5432 포트 사용 중
lsof -i :5432  # 프로세스 확인
kill -9 <PID>  # 종료

# 또는 docker-compose.yml에서 포트 변경
```
