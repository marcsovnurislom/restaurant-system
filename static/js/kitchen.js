// Экран кухни: карточки заказов обновляются по WebSocket без перезагрузки.
// Источник правды — сервер: сокет присылает заказ целиком, а после
// переподключения экран заново запрашивает список активных заказов.
(function () {
  const board = document.getElementById("board");
  if (!board) return;

  const role = board.dataset.role;
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;
  const connection = document.getElementById("connection");
  const orders = new Map();
  let reconnectDelay = 1000;

  const timeFormat = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });

  // --- Отрисовка ---------------------------------------------------------

  function minutesSince(iso) {
    return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function where(order) {
    if (order.type === "dine_in") return `Стол №${order.table_number}`;
    if (order.type === "delivery") return `Доставка: ${order.address}`;
    return `Самовывоз: ${order.customer_name}`;
  }

  function renderCard(order) {
    const card = el("article", `order-card order-card--${order.type}`);
    card.dataset.orderId = order.id;

    const head = el("header", "order-card__head");
    head.append(el("strong", "", `№${order.id}`));
    const age = el("span", "order-card__age");
    age.dataset.createdAt = order.created_at;
    age.textContent = `${timeFormat.format(new Date(order.created_at))} · ${minutesSince(order.created_at)} мин`;
    head.append(age);
    card.append(head);

    card.append(el("p", "order-card__where", where(order)));

    const items = el("ul", "order-card__items");
    for (const item of order.items) {
      const li = el("li");
      li.append(el("span", "order-card__qty", `${item.quantity}×`), ` ${item.name}`);
      items.append(li);
    }
    card.append(items);

    if (order.comment) card.append(el("p", "order-card__comment", order.comment));
    if (order.payment_status === "paid") card.append(el("span", "status status--completed", "Оплачен"));

    // Кнопки только для ролей, которым разрешён переход. Сервер всё равно проверит права
    const actions = order.actions.filter((a) => role === "admin" || a.roles.includes(role));
    if (actions.length) {
      const bar = el("div", "order-card__actions");
      for (const action of actions) {
        const isCancel = action.status === "cancelled";
        const button = el("button", isCancel ? "button button--secondary button--small" : "button button--small", action.label);
        button.type = "button";
        button.addEventListener("click", () => transition(order.id, action.status, button));
        bar.append(button);
      }
      card.append(bar);
    }
    return card;
  }

  function upsert(order) {
    const isNew = !orders.has(order.id);
    board.querySelector(`[data-order-id="${order.id}"]`)?.remove();

    const column = board.querySelector(`[data-column="${order.status}"] [data-cards]`);
    if (!column) {
      // Выполнен или отменён — убираем с экрана
      orders.delete(order.id);
    } else {
      orders.set(order.id, order);
      const card = renderCard(order);
      if (isNew) card.classList.add("order-card--fresh");
      // Порядок в колонке — по времени заказа, старые сверху
      const after = [...column.children].find(
        (other) => orders.get(Number(other.dataset.orderId))?.created_at > order.created_at,
      );
      column.insertBefore(card, after || null);
      if (isNew) beep();
    }
    updateCounts();
  }

  function replaceAll(list) {
    orders.clear();
    board.querySelectorAll("[data-cards]").forEach((column) => column.replaceChildren());
    for (const order of list) {
      orders.set(order.id, order);
      board.querySelector(`[data-column="${order.status}"] [data-cards]`)?.append(renderCard(order));
    }
    updateCounts();
  }

  function updateCounts() {
    board.querySelectorAll("[data-column]").forEach((column) => {
      column.querySelector("[data-count]").textContent = column.querySelector("[data-cards]").children.length;
    });
  }

  function refreshAges() {
    board.querySelectorAll("[data-created-at]").forEach((node) => {
      const created = node.dataset.createdAt;
      node.textContent = `${timeFormat.format(new Date(created))} · ${minutesSince(created)} мин`;
    });
  }

  // Короткий сигнал о новом заказе. Браузер разрешает звук только после первого клика на странице
  let audio;
  function beep() {
    try {
      audio = audio || new AudioContext();
      const osc = audio.createOscillator();
      osc.frequency.value = 880;
      osc.connect(audio.destination);
      osc.start();
      osc.stop(audio.currentTime + 0.15);
    } catch {
      /* звук недоступен — не страшно */
    }
  }

  // --- Действия ----------------------------------------------------------

  async function transition(orderId, status, button) {
    button.disabled = true;
    const url = board.dataset.transitionUrl.replace("{id}", orderId);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ status }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        alert(data.detail || "Не удалось сменить статус");
        button.disabled = false;
      }
      // При успехе карточку перерисует событие из сокета
    } catch {
      alert("Нет связи с сервером");
      button.disabled = false;
    }
  }

  // --- WebSocket ---------------------------------------------------------

  function setConnection(state, text) {
    connection.dataset.state = state;
    connection.textContent = text;
  }

  async function resync() {
    const response = await fetch(board.dataset.snapshotUrl, { headers: { Accept: "application/json" } });
    if (response.ok) replaceAll((await response.json()).orders);
  }

  function connect() {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${scheme}://${location.host}${board.dataset.socketPath}`);

    socket.addEventListener("open", () => {
      setConnection("online", "Онлайн");
      reconnectDelay = 1000;
      resync();
    });
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "order.updated") upsert(message.order);
    });
    socket.addEventListener("close", () => {
      setConnection("offline", "Нет связи, переподключаемся…");
      // Экспоненциальная задержка: не заваливаем сервер переподключениями
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    });
  }

  replaceAll(JSON.parse(document.getElementById("initial-orders").textContent));
  setInterval(refreshAges, 30000);
  connect();
})();
