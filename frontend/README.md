# AITU Assistant - Flutter фронтенд

Фронт для AI-ассистента AITU (бэкенд друга: https://github.com/CoLdEnnn/ai-powered-application).
Дизайн взят из Figma, язык только English. Сначала делаем под браузер на компе (Chrome), телефон - потом.

ВАЖНО: код написан без возможности его скомпилировать (в облаке, где я работаю, нет Flutter SDK).
Поэтому при первом запуске могут вылезти мелкие ошибки компиляции - кидай текст ошибки, поправим.

## Запустится ли на Маке в браузере?

Да. Flutter Web работает на macOS, нужен только Flutter и Google Chrome.

## 1. Установка (один раз)

```bash
brew install --cask flutter
flutter doctor
```

`flutter doctor` покажет, чего не хватает. Для веба нужен только Chrome (зелёная галочка у "Chrome - develop for the web"). Xcode/Android для веб-версии не нужны.

## 2. Создать проект и положить наш код

```bash
flutter create aitu_assistant --platforms=web
cd aitu_assistant
rm test/widget_test.dart
```

Потом скопируй из этой папки в `aitu_assistant/`:
- папку `lib/` (заменить существующую)
- файл `pubspec.yaml` (заменить)

```bash
flutter pub get
```

## 3. Запуск

Демо без бэкенда (фейковые ответы, чтобы посмотреть интерфейс):

```bash
flutter run -d chrome --dart-define=MOCK=true
```

С настоящим бэкендом (бэкенд должен быть запущен на порту 8000):

```bash
flutter run -d chrome --dart-define=API_BASE=http://127.0.0.1:8000
```

Адрес бэкенда можно поменять и прямо в приложении: Settings -> Backend address -> Save and check.

## 4. Бэкенд на Маке

В README друга инструкции для Windows (`llama-server.exe`). На Маке нужен macOS-вариант llama.cpp, например:

```bash
brew install llama.cpp
```

и в `config.json` бэкенда указать путь к `llama-server` в `llama_server_path` (`which llama-server`). Это надо проверить вместе с другом - я бэкенд на Маке не запускал.

## 5. CORS (без этого браузер не пустит запросы)

Во Flutter Web страница открывается на другом порту, чем бэкенд, поэтому в бэкенде нужно разрешить CORS. В `create_app` (файл с FastAPI-приложением) добавить:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Для защищённой версии потом заменить `"*"` на конкретный адрес фронта.

Альтернатива без CORS: собрать фронт (`flutter build web --base-href /static/flutter/`), положить `build/web` в `app/static/flutter` бэкенда и открывать с того же порта; тогда в Settings адрес бэкенда оставить пустым.

## 6. Телефон (когда дойдём)

- Тот же Wi-Fi: бэкенд запустить с `host: 0.0.0.0`, фронт с `--dart-define=API_BASE=http://IP_МАКА:8000`, открыть в Chrome на телефоне `http://IP_МАКА:ПОРТ`.
- Или туннель (Cloudflare Tunnel / ngrok).
- Мобильное приложение (Android/iOS) собирается из этого же кода: `flutter create` без `--platforms=web`.

## Что внутри

- `lib/api.dart` - запросы к `/api/health` и `/api/chat`, понятные ошибки (422 / 429 занято / 503 модель недоступна).
- `lib/state.dart` - состояние приложения.
- `lib/shell.dart` - навигация (на широком экране верхняя панель + левое меню, на узком - нижние вкладки).
- `lib/screens/` - Welcome, Chat (ответ + источники + Yes/No -> опрос), Topics, Calendar, Contacts, Settings, Survey.
- `lib/data.dart` - статичные темы, контакты, даты семестров (из базы знаний, снимок 2026-10-21).

Формат ответа бэкенда я читал по описанию репозитория, не по живому запуску. Если поля в JSON называются иначе, править надо `lib/models.dart`.

## Методология: Scrum

Спринты по 1-2 недели, бэклог, ревью и ретроспектива в конце каждого.

- Sprint 1: скелет Flutter, подключение `/api/chat`, экран чата с источниками.
- Sprint 2: Welcome и выбор аудитории, история вопросов, состояния ошибок (занято / модель недоступна).
- Sprint 3: Topics, Contacts, Calendar, опрос, полировка под телефон.
