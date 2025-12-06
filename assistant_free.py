import speech_recognition as sr
import pyttsx3
import os
import subprocess
import webbrowser
import json
from datetime import datetime
import requests
import threading
import queue

# Поддержка различных бесплатных AI провайдеров
try:
    from transformers import pipeline
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

class VoiceAssistantFree:
    def __init__(self, ai_backend='groq'):
        """
        ai_backend: 'groq', 'ollama', 'huggingface', 'offline'
        groq - бесплатный API (требует ключ, но бесплатный)
        ollama - локальная модель (полностью офлайн)
        huggingface - локальная модель через transformers
        offline - без AI, только команды
        """
        # Инициализация распознавания речи
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
        
        # Инициализация синтеза речи
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 180)
        self.engine.setProperty('volume', 0.9)
        
        # Получаем русский голос
        voices = self.engine.getProperty('voices')
        for voice in voices:
            if 'russian' in voice.name.lower():
                self.engine.setProperty('voice', voice.id)
                break
        
        # Настройка AI бэкенда
        self.ai_backend = ai_backend
        self.setup_ai_backend()
        
        # История разговора
        self.conversation_history = []
        
        # Очередь для озвучивания
        self.speech_queue = queue.Queue()
        self.speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.speech_thread.start()
        
        # Активное слово для активации
        self.wake_words = ['ассистент', 'помощник', 'компьютер']
        
        print(f"Голосовой ассистент инициализирован! AI: {ai_backend}")
        print(f"Используйте слова активации: {', '.join(self.wake_words)}")

    def setup_ai_backend(self):
        """Настройка выбранного AI бэкенда"""
        if self.ai_backend == 'groq':
            self.groq_api_key = os.getenv('GROQ_API_KEY')
            if not self.groq_api_key:
                print("ВНИМАНИЕ: GROQ_API_KEY не найден. Получите бесплатный ключ на https://console.groq.com")
                self.ai_backend = 'offline'
            else:
                print("✓ Groq API подключен (бесплатный, быстрый)")
                
        elif self.ai_backend == 'ollama':
            if not OLLAMA_AVAILABLE:
                print("ВНИМАНИЕ: Ollama не установлен. Установите: pip install ollama")
                print("И скачайте Ollama: https://ollama.ai")
                self.ai_backend = 'offline'
            else:
                try:
                    # Проверяем доступность Ollama
                    response = ollama.list()
                    print("✓ Ollama подключен (локальный, приватный)")
                    print(f"Доступные модели: {[m['name'] for m in response.get('models', [])]}")
                except Exception as e:
                    print(f"ВНИМАНИЕ: Ollama не запущен. Запустите сервер Ollama")
                    self.ai_backend = 'offline'
                    
        elif self.ai_backend == 'huggingface':
            if not HUGGINGFACE_AVAILABLE:
                print("ВНИМАНИЕ: transformers не установлен. Установите: pip install transformers torch")
                self.ai_backend = 'offline'
            else:
                print("Загрузка модели Hugging Face (первый запуск может занять время)...")
                try:
                    # Используем легкую русскоязычную модель
                    self.hf_pipeline = pipeline(
                        "text-generation",
                        model="sberbank-ai/rugpt3large_based_on_gpt2",
                        device=-1  # CPU
                    )
                    print("✓ Hugging Face модель загружена (локальная)")
                except Exception as e:
                    print(f"Ошибка загрузки модели: {e}")
                    self.ai_backend = 'offline'
                    
        elif self.ai_backend == 'offline':
            print("✓ Режим без AI (только команды)")

    def _speech_worker(self):
        """Отдельный поток для озвучивания текста"""
        while True:
            text = self.speech_queue.get()
            if text is None:
                break
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                print(f"Ошибка озвучивания: {e}")
            self.speech_queue.task_done()

    def speak(self, text):
        """Добавляет текст в очередь озвучивания"""
        print(f"Ассистент: {text}")
        self.speech_queue.put(text)

    def listen(self, timeout=5, phrase_time_limit=10):
        """Слушает микрофон и распознает речь"""
        with sr.Microphone() as source:
            print("Слушаю...")
            try:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                text = self.recognizer.recognize_google(audio, language='ru-RU')
                print(f"Вы сказали: {text}")
                return text.lower()
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                print(f"Ошибка сервиса распознавания: {e}")
                return None
            except Exception as e:
                print(f"Ошибка: {e}")
                return None

    def get_ai_response_groq(self, user_input):
        """Получает ответ от Groq (бесплатный, быстрый API)"""
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            }
            
            self.conversation_history.append({"role": "user", "content": user_input})
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
            
            data = {
                "model": "mixtral-8x7b-32768",  # Бесплатная мощная модель
                "messages": [
                    {"role": "system", "content": "Ты полезный голосовой ассистент. Отвечай кратко и по делу на русском языке."},
                    *self.conversation_history
                ],
                "max_tokens": 200,
                "temperature": 0.7
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            answer = response.json()['choices'][0]['message']['content']
            self.conversation_history.append({"role": "assistant", "content": answer})
            return answer
            
        except Exception as e:
            return f"Ошибка Groq API: {str(e)}"

    def get_ai_response_ollama(self, user_input):
        """Получает ответ от Ollama (локальная модель)"""
        try:
            # Используем легкую русскоязычную модель
            response = ollama.chat(
                model='llama2',  # Или 'mistral', 'gemma2'
                messages=[
                    {'role': 'system', 'content': 'Ты полезный голосовой ассистент. Отвечай кратко на русском.'},
                    {'role': 'user', 'content': user_input}
                ],
                options={'temperature': 0.7, 'num_predict': 100}
            )
            return response['message']['content']
        except Exception as e:
            return f"Ошибка Ollama: {str(e)}. Убедитесь, что Ollama запущен и модель загружена (ollama pull llama2)"

    def get_ai_response_huggingface(self, user_input):
        """Получает ответ от локальной Hugging Face модели"""
        try:
            prompt = f"Вопрос: {user_input}\nОтвет:"
            result = self.hf_pipeline(
                prompt,
                max_length=150,
                num_return_sequences=1,
                temperature=0.7,
                do_sample=True
            )
            answer = result[0]['generated_text'].replace(prompt, '').strip()
            return answer if answer else "Извините, не смог сформулировать ответ"
        except Exception as e:
            return f"Ошибка Hugging Face: {str(e)}"

    def get_ai_response(self, user_input):
        """Получает ответ от выбранного AI бэкенда"""
        if self.ai_backend == 'groq':
            return self.get_ai_response_groq(user_input)
        elif self.ai_backend == 'ollama':
            return self.get_ai_response_ollama(user_input)
        elif self.ai_backend == 'huggingface':
            return self.get_ai_response_huggingface(user_input)
        else:
            return "AI не настроен. Используйте команды или настройте AI бэкенд."

    def execute_command(self, command):
        """Выполняет системные команды"""
        # Открытие приложений
        if 'открой браузер' in command or 'открой интернет' in command:
            webbrowser.open('https://www.google.com')
            return "Открываю браузер"
        
        if 'открой youtube' in command or 'открой ютуб' in command:
            webbrowser.open('https://www.youtube.com')
            return "Открываю YouTube"
        
        if 'открой github' in command or 'открой гитхаб' in command:
            webbrowser.open('https://www.github.com')
            return "Открываю GitHub"
        
        # Время и дата
        if 'сколько времени' in command or 'который час' in command:
            now = datetime.now()
            return f"Сейчас {now.strftime('%H:%M')}"
        
        if 'какое сегодня число' in command or 'какая дата' in command:
            now = datetime.now()
            return f"Сегодня {now.strftime('%d.%m.%Y')}"
        
        # Системные команды
        if 'выключи компьютер' in command:
            self.speak("Выключаю компьютер через 60 секунд. Скажите 'отмена', чтобы остановить.")
            subprocess.run(['shutdown', '/s', '/t', '60'])
            return "Компьютер будет выключен через 60 секунд"
        
        if 'отмена' in command:
            subprocess.run(['shutdown', '/a'])
            return "Выключение отменено"
        
        # Поиск в интернете
        if 'найди' in command or 'поищи' in command:
            search_query = command.replace('найди', '').replace('поищи', '').strip()
            if search_query:
                webbrowser.open(f'https://www.google.com/search?q={search_query}')
                return f"Ищу информацию про {search_query}"
        
        return None

    def run(self):
        """Основной цикл работы ассистента"""
        self.speak(f"Голосовой ассистент запущен. Режим AI: {self.ai_backend}. Скажите слово активации.")
        
        waiting_for_wake = True
        
        while True:
            try:
                if waiting_for_wake:
                    command = self.listen(timeout=10)
                    if command and any(word in command for word in self.wake_words):
                        self.speak("Да, слушаю")
                        waiting_for_wake = False
                else:
                    command = self.listen(timeout=5, phrase_time_limit=10)
                    
                    if not command:
                        waiting_for_wake = True
                        continue
                    
                    # Команды выхода
                    if 'выход' in command or 'хватит' in command or 'стоп' in command:
                        self.speak("До свидания!")
                        break
                    
                    # Переход в режим ожидания
                    if 'спасибо' in command or 'всё' in command:
                        self.speak("Обращайтесь")
                        waiting_for_wake = True
                        continue
                    
                    # Выполнение команд
                    response = self.execute_command(command)
                    
                    if response:
                        self.speak(response)
                    else:
                        # Используем AI
                        ai_response = self.get_ai_response(command)
                        self.speak(ai_response)
                    
            except KeyboardInterrupt:
                self.speak("Завершение работы")
                break
            except Exception as e:
                print(f"Ошибка в основном цикле: {e}")
                continue
        
        self.speech_queue.put(None)
        self.speech_thread.join()

if __name__ == "__main__":
    import sys
    
    # Выбор AI бэкенда из аргументов командной строки
    backend = 'groq'  # По умолчанию
    
    if len(sys.argv) > 1:
        backend = sys.argv[1]
    
    print("\n=== Доступные AI бэкенды ===")
    print("groq - Бесплатный быстрый API (требует GROQ_API_KEY)")
    print("ollama - Локальная модель (требует Ollama)")
    print("huggingface - Локальная модель (требует transformers)")
    print("offline - Без AI, только команды")
    print(f"\nИспользуется: {backend}")
    print("\nДля смены: python assistant_free.py <backend>\n")
    
    assistant = VoiceAssistantFree(ai_backend=backend)
    assistant.run()
