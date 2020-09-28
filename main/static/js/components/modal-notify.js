class ModalNotify extends ModalDialog {
  constructor() {
    super();

    this._warningIcon = document.createElement("modal-warning");
    this._header.insertBefore(this._warningIcon, this._titleDiv);

    this._successIcon = document.createElement("modal-success");
    this._header.insertBefore(this._successIcon, this._titleDiv);

    this._message = document.createElement("p");
    this._message.setAttribute("class", "text-semibold py-3");
    this._main.appendChild(this._message);

    this._accept = document.createElement("button");
    this._accept.setAttribute("class", "btn btn-clear");
    this._accept.textContent = "Close";
    this._footer.appendChild(this._accept);

    this._accept.addEventListener("click", evt => {
      this._closeCallback();
    });
  }

  init(title, message, error_or_ok) {
    this._title.nodeValue = title;
    this._message.textContent = message;
    if (error_or_ok == 'error') {
      this._warningIcon.style.display = "block";
      this._successIcon.style.display = "none";
      this._accept.classList.remove("btn-charcoal");
      this._accept.classList.add("btn-red");
    } else {
      this._warningIcon.style.display = "none";
      this._successIcon.style.display = "block";
      this._accept.classList.remove("btn-red");
      this._accept.classList.add("btn-purple");
    }
  }

  static get observedAttributes() {
    return ModalDialog.observedAttributes;
  }

  attributeChangedCallback(name, oldValue, newValue) {
    ModalDialog.prototype.attributeChangedCallback.call(this, name, oldValue, newValue);
    switch (name) {
      case "is-open":
        break;
    }
  }
}

customElements.define("modal-notify", ModalNotify);