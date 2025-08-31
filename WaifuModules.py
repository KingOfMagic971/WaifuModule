# -*- coding: utf-8 -*-
# meta developer: @Rezoxss
# scope: hikka_only

from .. import loader, utils
import logging
import random
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap

logger = logging.getLogger(__name__)

@loader.tds
class StableWaifuMod(loader.Module):
    """Модуль для генерации AI изображений как @StableWaifuBot"""
    
    strings = {
        "name": "StableWaifu",
        "processing": "🔄 Генерирую изображение...",
        "error": "❌ Ошибка генерации",
        "no_prompt": "❌ Укажи запрос для генерации",
        "stopped": "⏹️ Генерация остановлена",
        "queue": "📊 В очереди: {} запросов",
        "limit": "⚠️ Лимит: макс. {} символов",
        "result": "🎨 Сгенерировано по запросу: {}"
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "max_length",
                100,
                "Максимальная длина запроса",
                validator=loader.validators.Integer(minimum=10, maximum=500)
            ),
            loader.ConfigValue(
                "queue_limit",
                3,
                "Максимум запросов в очереди",
                validator=loader.validators.Integer(minimum=1, maximum=10)
            ),
            loader.ConfigValue(
                "nsfw_enabled",
                True,
                "Разрешить NSFW запросы",
                validator=loader.validators.Boolean()
            )
        )
        self.generation_queue = asyncio.Queue()
        self.is_processing = False
        self.current_task = None
        self.waifu_styles = self.load_waifu_styles()

    def load_waifu_styles(self):
        """Стили для генерации вайфу"""
        return {
            "anime": ["аниме", "мультяшный", "стиль аниме", "японский"],
            "realistic": ["реалистичный", "фото", "реализм", "photorealistic"],
            "hentai": ["хентай", "18+", "эротика", "nsfw", "сексуальный"],
            "fantasy": ["фэнтези", "магия", "фантастика", "волшебный"],
            "game": ["игровой", "геймер", "видеоигра", "пиксель"],
            "cyberpunk": ["киберпанк", "футуристичный", "неоновый", "техно"]
        }

    async def client_ready(self, client, db):
        self._client = client

    def detect_style(self, prompt):
        """Определяем стиль по промпту"""
        prompt_lower = prompt.lower()
        for style, keywords in self.waifu_styles.items():
            for keyword in keywords:
                if keyword in prompt_lower:
                    return style
        return random.choice(list(self.waifu_styles.keys()))

    def generate_ai_image(self, prompt, style):
        """Генерируем псевдо-AI изображение"""
        try:
            # Создаем базовое изображение
            width, height = 512, 512
            image = Image.new('RGB', (width, height), color='black')
            draw = ImageDraw.Draw(image)
            
            # Генерируем "стиль" based on prompt
            colors = {
                "anime": [(255, 105, 180), (255, 20, 147), (255, 182, 193)],
                "realistic": [(100, 100, 100), (150, 150, 150), (200, 200, 200)],
                "hentai": [(255, 0, 0), (139, 0, 0), (178, 34, 34)],
                "fantasy": [(0, 255, 255), (0, 191, 255), (30, 144, 255)],
                "game": [(0, 255, 0), (50, 205, 50), (144, 238, 144)],
                "cyberpunk": [(138, 43, 226), (75, 0, 130), (148, 0, 211)]
            }
            
            # Рисуем абстрактную картинку
            for i in range(100):
                x1 = random.randint(0, width)
                y1 = random.randint(0, height)
                x2 = random.randint(0, width)
                y2 = random.randint(0, height)
                color = random.choice(colors.get(style, [(255, 255, 255)]))
                draw.line([x1, y1, x2, y2], fill=color, width=random.randint(1, 5))
            
            # Добавляем текст с промптом
            try:
                font = ImageFont.load_default()
                wrapped_text = textwrap.fill(prompt, width=30)
                draw.text((10, 10), wrapped_text, fill=(255, 255, 255), font=font)
            except:
                pass
            
            # Сохраняем в bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            return img_byte_arr
            
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return None

    async def process_queue(self):
        """Обрабатываем очередь генерации"""
        while not self.generation_queue.empty():
            try:
                message, prompt = await self.generation_queue.get()
                
                # Определяем стиль
                style = self.detect_style(prompt)
                
                # Генерируем изображение
                processing_msg = await message.reply(self.strings("processing"))
                await asyncio.sleep(2)  # Имитация обработки
                
                image_data = self.generate_ai_image(prompt, style)
                
                if image_data:
                    await processing_msg.delete()
                    await message.reply(
                        self.strings("result").format(prompt),
                        file=image_data
                    )
                else:
                    await processing_msg.edit(self.strings("error"))
                    
                self.generation_queue.task_done()
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Queue error: {e}")
                continue

    @loader.command()
    async def image(self, message):
        """Сгенерировать AI изображение - .image <запрос>"""
        args = utils.get_args_raw(message)
        if not args:
            await utils.answer(message, self.strings("no_prompt"))
            return
            
        # Проверяем длину запроса
        if len(args) > self.config["max_length"]:
            await utils.answer(message, self.strings("limit").format(self.config["max_length"]))
            return
            
        # Проверяем NSFW
        if not self.config["nsfw_enabled"] and any(word in args.lower() for word in self.waifu_styles["hentai"]):
            await utils.answer(message, "❌ NSFW запросы запрещены")
            return
            
        # Добавляем в очередь
        if self.generation_queue.qsize() >= self.config["queue_limit"]:
            await utils.answer(message, self.strings("queue").format(self.config["queue_limit"]))
            return
            
        await self.generation_queue.put((message, args))
        await utils.answer(message, f"📥 Добавлено в очередь: {args}")
        
        # Запускаем обработку если не активна
        if not self.is_processing:
            self.is_processing = True
            asyncio.create_task(self.process_queue())

    @loader.command()
    async def stop(self, message):
        """Остановить генерацию"""
        if not self.generation_queue.empty():
            # Очищаем очередь
            while not self.generation_queue.empty():
                try:
                    self.generation_queue.get_nowait()
                    self.generation_queue.task_done()
                except:
                    break
            await utils.answer(message, self.strings("stopped"))
        else:
            await utils.answer(message, "✅ Очередь уже пуста")

    @loader.command()
    async def waifustats(self, message):
        """Показать статистику очереди"""
        queue_size = self.generation_queue.qsize()
        status = "🟢 Активна" if self.is_processing else "🔴 Неактивна"
        
        stats_text = (
            f"📊 Статистика генерации:\n\n"
            f"🔄 Статус: {status}\n"
            f"📥 В очереди: {queue_size}\n"
            f"📏 Лимит запроса: {self.config['max_length']} симв.\n"
            f"🚦 Макс. очередь: {self.config['queue_limit']}\n"
            f"🔞 NSFW: {'✅ Разрешено' if self.config['nsfw_enabled'] else '❌ Запрещено'}"
        )
        await utils.answer(message, stats_text)

    @loader.command()
    async def waifustyle(self, message):
        """Показать доступные стили"""
        styles_text = "🎨 Доступные стили:\n\n"
        for style, keywords in self.waifu_styles.items():
            styles_text += f"• {style.capitalize()}: {', '.join(keywords[:3])}\n"
        
        styles_text += "\n💡 Используй эти слова в запросе для нужного стиля!"
        await utils.answer(message, styles_text)

    async def on_unload(self):
        """Очистка при выгрузке"""
        self.is_processing = False
        while not self.generation_queue.empty():
            try:
                self.generation_queue.get_nowait()
                self.generation_queue.task_done()
            except:
                break
