# 🎬 CineMatch - Intelligent Movie Discovery Platform

<div align="center">
  <p>A real-time movie discovery platform with AI-powered recommendations, social features, and personalized insights.</p>
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/React-18+-61DAFB.svg" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/TMDB-API-01D277.svg" alt="TMDB">
  <img src="https://img.shields.io/badge/TensorFlow-2.13+-FF6F00.svg" alt="TensorFlow">
  <img src="https://img.shields.io/badge/Redis-Cache-DC382D.svg" alt="Redis">
  <img src="https://img.shields.io/badge/Status-Enhanced-success.svg" alt="Status">
</div>

## 🎯 Overview

CineMatch is an intelligent, real-time movie discovery platform that combines The Movie Database (TMDB) API with advanced AI/ML algorithms to deliver personalized movie recommendations that evolve with user preferences and cinema trends. Features hybrid recommendation engines, social viewing tools, and mood-based suggestions.

## ✨ Core Features

### 🤖 **AI-Powered Recommendations**
- **Hybrid Recommendation Engine** - Combines content-based and collaborative filtering
- **Mood-Based Suggestions** - AI analyzes sentiment from reviews and descriptions
- **Continuous Learning** - Adapts to changing user preferences in real-time

### 🎬 **Real-Time Movie Discovery**
- **Live Content Updates** - Automatic sync with latest TMDB releases
- **Dynamic Trending** - Real-time trending movies and popularity shifts
- **Instant Notifications** - Alerts for new movies matching your taste
- **Smart Search** - AI-enhanced search with natural language processing

### 👥 **Social & Group Features**
- **Watch Party Matcher** - Find movies perfect for group viewing
- **Social Recommendations** - Learn from friends' viewing patterns
- **Spoiler-Free Reviews** - NLP-powered review summaries without plot reveals
- **Community Insights** - Aggregated user sentiment and trends

### ⭐ **Enhanced User Experience**
- **Personal Rating System** with predictive suggestions
- **Viewing History Analysis** - Pattern recognition and taste evolution
- **Interactive Visualizations** - D3.js powered movie connection graphs

## 🛠️ Enhanced Tech Stack

**Backend:**
- FastAPI, PostgreSQL, Redis Cache
- **ML/AI**: TensorFlow/PyTorch, BERT, Word2Vec, Surprise Library
- **Task Queue**: Celery with Redis broker
- **Scheduling**: Apache Airflow for automated data pipelines
- **Authentication**: JWT with refresh token rotation

**Frontend:**
- React 18+, Tailwind CSS, TypeScript
- **Visualization**: D3.js for movie connection graphs
- **Real-time**: WebSocket connections for live updates
- **State Management**: Context API with custom hooks

**Data & ML Pipeline:**
- Apache Airflow for orchestration
- Automated model training and deployment
- Real-time recommendation serving
- Background sentiment analysis

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- TMDB API Key ([Get one here](https://www.themoviedb.org/settings/api))
- Python 3.9+
- Node.js 16+

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/CineMatch.git
   cd CineMatch
   ```

2. **Backend Setup**
   ```bash
   cd backend
   # Create .env file
   cat > .env << EOF
   TMDB_API_KEY=your_api_key_here
   DATABASE_URL=postgresql://cinematch_user:cinematch_password_123@localhost:5432/cinematch_db
   REDIS_URL=redis://localhost:6379/0
   SECRET_KEY=your-secret-key
   ML_MODEL_PATH=./models/
   CELERY_BROKER_URL=redis://localhost:6379/1
   EOF
   
   # Start all services
   docker-compose up -d
   python init_database.py
   python train_models.py  # Initialize ML models
   python run_server.py
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm run build:tailwind
   npm start
   ```

4. **Start Background Tasks**
   ```bash
   cd backend
   celery -A app.celery worker --loglevel=info  # New terminal
   celery -A app.celery beat --loglevel=info    # Another terminal
   ```

5. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000/docs
   - Admin Dashboard: http://localhost:3000/admin

## 📁 Enhanced Project Structure

```
CineMatch/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   │   ├── movies/      # Movie operations
│   │   │   ├── recommendations/ # AI recommendation engine
│   │   │   ├── social/      # Social features
│   │   │   └── analytics/   # User analytics
│   │   ├── core/            # Configuration & utilities
│   │   ├── models/          # Database models
│   │   ├── services/        # External service integrations
│   │   │   ├── tmdb/        # TMDB API client
│   │   │   ├── ml/          # Machine learning services
│   │   │   └── cache/       # Redis caching layer
│   │   ├── tasks/           # Celery background tasks
│   │   ├── ml_models/       # Trained ML models
│   │   └── main.py
│   ├── tests/               # Comprehensive test suite
│   ├── docker-compose.yml
│   ├── airflow/            # Data pipeline DAGs
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable React components
│   │   │   ├── common/      # Common UI components
│   │   │   ├── movies/      # Movie-specific components
│   │   │   ├── social/      # Social features UI
│   │   │   └── recommendations/ # Recommendation UI
│   │   ├── pages/           # Page components
│   │   ├── services/        # API services & WebSocket
│   │   ├── hooks/           # Custom React hooks
│   │   ├── utils/           # Utility functions
│   │   ├── store/           # State management
│   │   └── App.js
│   ├── public/
│   └── package.json
├── ml_pipeline/            # Offline ML training scripts
├── docs/                   # API documentation
└── README.md
```

## 🔧 Environment Variables

Create `backend/.env`:
```env
# Core Configuration
TMDB_API_KEY=your_tmdb_api_key
DATABASE_URL=postgresql://cinematch_user:cinematch_password_123@localhost:5432/cinematch_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-minimum-32-characters

# ML/AI Configuration
ML_MODEL_PATH=./ml_models/
HUGGINGFACE_API_KEY=your_huggingface_api_key
OPENAI_API_KEY=your_openai_api_key  # Optional: for advanced NLP

# Background Tasks
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# External Services
NOTIFICATION_SERVICE_URL=http://localhost:8001
ANALYTICS_SERVICE_URL=http://localhost:8002

# Development
DEBUG=True
BACKEND_CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
```

## 📚 Enhanced API Endpoints

### Core Movie Operations
- `GET /api/v1/movies/` - Get movies with intelligent filtering
- `GET /api/v1/movies/search` - AI-enhanced search with NLP
- `GET /api/v1/movies/{id}/similar` - Content-based similar movies

### AI Recommendations
- `GET /api/v1/recommendations/personal` - Personalized recommendations
- `GET /api/v1/recommendations/mood/{mood}` - Mood-based suggestions
- `GET /api/v1/recommendations/group` - Watch party recommendations
- `POST /api/v1/recommendations/feedback` - Recommendation feedback loop

### Social Features
- `GET /api/v1/social/friends/recommendations` - Friend-based suggestions
- `POST /api/v1/social/watchparty/create` - Create watch party session
- `GET /api/v1/social/reviews/spoiler-free/{movie_id}` - Spoiler-free reviews

### User Analytics
- `GET /api/v1/analytics/taste-profile` - User taste analysis
- `GET /api/v1/analytics/viewing-patterns` - Viewing behavior insights
- `POST /api/v1/analytics/interaction` - Track user interactions

### Authentication & User Management
- `POST /api/v1/auth/register` - Enhanced user registration
- `POST /api/v1/auth/login` - JWT authentication
- `POST /api/v1/auth/refresh` - Token refresh
- `GET /api/v1/users/preferences` - User preference management

## 🧠 Machine Learning Pipeline

### Model Training
```bash
cd ml_pipeline
python train_collaborative_filter.py  # Collaborative filtering model
python train_content_based.py         # Content-based model  
python train_sentiment_analyzer.py    # Review sentiment analysis
python train_mood_classifier.py       # Mood-based classifier
```

### Model Deployment
- Models are automatically versioned and deployed via MLflow
- A/B testing framework for recommendation algorithms
- Real-time model performance monitoring

## 🔄 Real-Time Features

- **Live Updates**: WebSocket connections for instant content updates
- **Background Processing**: Celery tasks for heavy ML computations
- **Caching Strategy**: Multi-layer Redis caching for optimal performance
- **Data Pipeline**: Scheduled data refreshes via Airflow

## 📊 Data Visualization

### Interactive Movie Visualizations
- **Movie Similarity Networks**: D3.js powered interactive graphs showing movie relationships
- **User Taste Evolution**: Timeline visualizations of preference changes
- **Genre Distribution**: Dynamic pie charts and radar charts
- **Recommendation Confidence**: Visual confidence scores for suggestions
- **Social Connections**: Network graphs of friend recommendations

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest tests/ -v --cov=app

# Frontend tests  
cd frontend
npm run test

# Integration tests
npm run test:integration

# ML model tests
cd ml_pipeline
python -m pytest model_tests/ -v
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/ai-enhancement`)
3. Commit changes (`git commit -m 'Add AI-powered mood recommendations'`)
4. Push to branch (`git push origin feature/ai-enhancement`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 for Python code
- Use TypeScript for new frontend components
- Add comprehensive tests for ML models
- Update API documentation for new endpoints


---

<div align="center">
  <p>Made with ❤️ and 🤖 by Ayushmaan Gupta</p>
  <p><strong>CineMatch - Where AI meets Cinema</strong></p>
</div>
