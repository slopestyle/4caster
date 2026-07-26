"""telegram_ui: только отображение, без доменной логики (MB-5).

В срезе рендерит текстовую карточку прогноза (§15.3). Inline-клавиатуры,
графика (метеограмма/spaghetti/heat-map) и aiogram-хендлеры — Фаза 5.
"""

from fourcaster.modules.telegram_ui.renderers import render_forecast_card

__all__ = ["render_forecast_card"]
