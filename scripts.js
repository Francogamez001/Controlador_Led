window.setEsp32Connected = (connected) => {
	const status = document.querySelector("#connection-status");
	const label = document.querySelector("#connection-label");
	status.classList.toggle("conectado", connected);
	label.textContent = connected ? "ESP32 conectado" : "ESP32 desconectado";
};
