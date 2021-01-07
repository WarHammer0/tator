class ProjectDescription extends TatorElement {
  constructor() {
    super();

    const div = document.createElement("div");
    div.setAttribute("class", "projects__description d-flex py-2 f2 text-gray");
    this._shadow.appendChild(div);

    this._numFiles = document.createTextNode("");
    div.appendChild(this._numFiles);

    const span = document.createElement("span");
    span.setAttribute("class", "px-2");
    span.textContent = "·";
    div.appendChild(span);

    this._size = document.createTextNode("");
    div.appendChild(this._size);

    const span1 = document.createElement("span");
    span1.setAttribute("class", "px-2");
    span1.textContent = "·";
    div.appendChild(span1);

    this._hours = document.createTextNode("");
    div.appendChild(this._hours);

    const progDiv = document.createElement("div");
    progDiv.setAttribute("class", "px-6 d-flex flex-items-center");
    div.appendChild(progDiv);

    this._progress = document.createElement("progress");
    this._progress.setAttribute("class", "progress");
    this._progress.setAttribute("id", "progress");
    this._progress.setAttribute("max", "100");
    this._progress.setAttribute("value", "0");
    this._progress.style.visibility = "hidden";
    progDiv.appendChild(this._progress);

    this._label = document.createElement("label");
    this._label.setAttribute("class", "d-flex px-2");
    this._label.setAttribute("for", "progress");
    this._label.style.visibility = "hidden";
    progDiv.appendChild(this._label);

    this._numProcesses = null;
  }

  init(project) {
    let fileLabel = " files";
    if (project.num_files == 1) {
      fileLabel = " file";
    }
    this._numFiles.nodeValue = project.num_files + fileLabel;
    let num = project.size;
    let label = "B";
    if (project.size > 1e12) {
      num = num / 1e12;
      label = "TB";
    } else if (num > 1e9) {
      num = num / 1e9;
      label = "GB";
    } else if (num > 1e6) {
      num = num / 1e6;
      label = "MB";
    } else if (num > 1e3) {
      num = num / 1e3;
      label = "KB";
    }
    this._size.nodeValue = Number(num).toFixed(1) + label;
    let duration = project.duration;
    let label1 = "seconds";
    if (duration > 3600) {
      duration = duration / 3600;
      label1 = "hours";
    } else if (duration > 60) {
      duration = duration / 60;
      label1 = "minutes";
    }
    this._hours.nodeValue = Number(duration).toFixed(1) + " " + label1;
  }
}

customElements.define("project-description", ProjectDescription);
