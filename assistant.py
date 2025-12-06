import speech_recognition as sr
import pyttsx3
import openai
import os
import subprocess
import webbrowser
import json
from datetime import datetime
import requests
import threading
import queue

class VoiceAssistant:
    def __init__(self):
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
        
        # API ключи (загружаются из переменных окружения)
        self.openai_key = os.getenv('OPENAI_API_KEY')
        if self.openai_key:
            openai.api_key = self.openai_key
        
        # История разговора для контекста
        self.conversation_history = []
        
        # Очередь для озвучивания
        self.speech_queue = queue.Queue()
        self.speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.speech_thread.start()
        
        # Активное слово для активации
        self.wake_words = ['ассистент', 'помощник', 'компьютер']
        
        print("Голосовой ассистент инициализирован!")
        print(f"Используйте слова активации: {', '.join(self.wake_words)}")

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
                # Калибровка под шум окружения
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                
                # Распознавание с использованием Google Speech Recognition
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

    def get_ai_response(self, user_input):
        """Получает ответ от OpenAI GPT"""
        if not self.openai_key:
            return "API ключ OpenAI не настроен. Установите переменную окружения OPENAI_API_KEY."
        
        try:
            # Добавляем сообщение пользователя в историю
            self.conversation_history.append({"role": "user", "content": user_input})
            
            # Ограничиваем историю последними 10 сообщениями
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
            
            # Отправляем запрос к GPT
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты полезный голосовой ассистент. Отвечай кратко и по делу на русском языке."},
                    *self.conversation_history
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            answer = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": answer})
            return answer
            
        except Exception as e:
            return f"Ошибка при обращении к AI: {str(e)}"

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
        
        # Погода
        if 'погода' in command:
            return self.get_weather()
        
        return None

    def get_weather(self):
        """Получает информацию о погоде"""
        # Здесь можно использовать API погоды, например OpenWeatherMap
        # Для демонстрации возвращаем заглушку
        return "Для получения погоды настройте API ключ OpenWeatherMap в коде"

    def run(self):
        """Основной цикл работы ассистента"""
        self.speak("Голосовой ассистент запущен. Скажите слово активации, чтобы начать.")
        
        waiting_for_wake = True
        
        while True:
            try:
                if waiting_for_wake:
                    # Ждем слово активации
                    command = self.listen(timeout=10)
                    if command and any(word in command for word in self.wake_words):
                        self.speak("Да, слушаю")
                        waiting_for_wake = False
                else:
                    # Слушаем команду
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
                        # Если команда не распознана, используем AI
                        ai_response = self.get_ai_response(command)
                        self.speak(ai_response)
                    
            except KeyboardInterrupt:
                self.speak("Завершение работы")
                break
            except Exception as e:
                print(f"Ошибка в основном цикле: {e}")
                continue
        
        # Завершение работы
        self.speech_queue.put(None)
        self.speech_thread.join()

if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run()
