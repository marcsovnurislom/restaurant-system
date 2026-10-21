// Подгружает свободное время при смене даты или количества гостей.
// Без JS форма тоже работает: сервер всё равно проверит слот и вернёт ошибку.
(function () {
  const form = document.querySelector("[data-availability-url]");
  if (!form) return;

  const dateInput = form.elements.date;
  const guestsInput = form.elements.guests_count;
  const timeSelect = form.elements.time;
  const status = document.getElementById("slots-status");
  const url = form.dataset.availabilityUrl;
  let requestId = 0;

  async function refreshSlots() {
    const guests = Number(guestsInput.value);
    if (!dateInput.value || !guests) return;

    const currentRequest = ++requestId;
    const params = new URLSearchParams({ date: dateInput.value, guests: String(guests) });
    status.textContent = "Проверяем свободное время…";

    try {
      const response = await fetch(`${url}?${params}`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(String(response.status));
      const data = await response.json();
      // Ответ на устаревший запрос (пользователь уже сменил дату) игнорируем
      if (currentRequest !== requestId) return;
      renderSlots(data.slots);
    } catch {
      if (currentRequest === requestId) status.textContent = "";
    }
  }

  function renderSlots(slots) {
    const previous = timeSelect.value;
    timeSelect.replaceChildren(...slots.map((slot) => new Option(slot, slot)));
    if (slots.includes(previous)) timeSelect.value = previous;
    timeSelect.disabled = slots.length === 0;
    status.textContent = slots.length
      ? `Свободных слотов: ${slots.length}`
      : "На этот день свободных столов нет. Попробуйте другую дату.";
  }

  dateInput.addEventListener("change", refreshSlots);
  guestsInput.addEventListener("change", refreshSlots);
  refreshSlots();
})();
