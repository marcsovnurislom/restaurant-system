// Живой статус заказа для гостя: обновления приходят по WebSocket.
(function () {
  const root = document.getElementById("order");
  if (!root) return;

  const statusBadge = root.querySelector("[data-status]");
  const paidBadge = root.querySelector("[data-paid]");
  const timeline = root.querySelector("[data-timeline]");
  let reconnectDelay = 1000;

  function render(order) {
    statusBadge.textContent = order.status_display;
    statusBadge.className = `status status--${order.status}`;
    paidBadge.hidden = order.payment_status !== "paid";

    // Кнопки «Оплатить» и «Отменить» исчезают, когда действие стало недоступно
    const pay = root.querySelector("[data-pay]");
    if (pay && !order.awaits_online_payment) pay.remove();
    const cancel = root.querySelector("[data-cancel]");
    if (cancel && !order.can_cancel) cancel.remove();

    timeline.replaceChildren(
      ...order.history.map((entry) => {
        const li = document.createElement("li");
        const time = document.createElement("time");
        time.textContent = entry.time;
        li.append(time, ` ${entry.status_display}`);
        return li;
      }),
    );
  }

  function connect() {
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${scheme}://${location.host}${root.dataset.socketPath}`);
    socket.addEventListener("open", () => {
      reconnectDelay = 1000;
    });
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "order.updated") render(message.order);
    });
    socket.addEventListener("close", (event) => {
      // 4404 — заказа нет, переподключаться бессмысленно
      if (event.code === 4404) return;
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    });
  }

  connect();
})();
