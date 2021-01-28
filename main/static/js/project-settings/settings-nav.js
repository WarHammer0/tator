class SettingsNav extends TatorElement {
  constructor() {
    super();

    //@TODO - this could be abstract component

    // main structure
    this.nav = document.createElement("nav");
    this.nav.setAttribute("class", "SideNav rounded-2 col-3");
    this.nav.style.float = "left";

    // Prep the modal.
    //this.modal = document.createElement("modal-dialog");
    //this.nav.appendChild(this.modal);

    this._shadow.appendChild(this.nav);
  }

  _addProjectNav(){
    return this._addItem({
      "name":"Project",
      "type":"project",
      "linkData":"#projectMain"
    });
  }

  _init({
    media = "",
    localization = "",
    leaf = "",
    state = "",
  } = {}){
    console.log(`${this.tagName} init.`);
    // first Nav, static added during init
    this._addProjectNav();
    //this._getMediaNav( JSON.parse(media) );
    this._addNav("Media", JSON.parse(media));
    this._addNav("Localization", JSON.parse(localization));
    this._addNav("Leaf", JSON.parse(leaf));
    this._addNav("State", JSON.parse(state));


  }

  /*_getMediaNav(data){
    if(data.length > 0){
      let videoTypeArray = [];
      let imageTypeArray = [];
      let multiTypeArray = [];

      //eval data into groups
      for(let o of data){
        if( o.dtype == "video" ){
          videoTypeArray.push(o);
        } else if( o.dtype == "image" ){
          imageTypeArray.push(o);
        } else if( o.dtype == "multi" ){
          multiTypeArray.push(o);
        }else{
          console.log("Not a recognized media type.");
          console.log(o);
        }
      }

      //console.log("video");
      //console.log(videoTypeArray);

      // Add navs with items
      if(videoTypeArray.length > 0 ) this._addNav("Video", videoTypeArray);
      if(imageTypeArray.length > 0 ) this._addNav("Image", imageTypeArray);
      if(multiTypeArray.length > 0 ) this._addNav("Multi", multiTypeArray);

    } else {
      return console.log("Project contains no Media Types.");
    }
  }*/

  _addNav(typeCamel, a){
    if(a.length > 0){
      let type = typeCamel.toLowerCase();
      return this._addHeadingWithSubItems({
        "name" : typeCamel + " Type",
        "type" : type,
        "subItems" : a
      });
    } else {
      console.log(`${typeCamel} has no navigation items.`);
    }

  }



  _addItem({name = "Default", type = "project", mediaId = -1, linkData = "#"} = {} ){
    //let item = document.createElement("h3");
    //item.setAttribute("class", "py-3 lh-condensed text-semibold");
    let item = document.createElement("a");
    item.setAttribute("class", "SideNav-item ");
    item.href = linkData;
    item.title = type.replace(/[^a-zA-Z0-9]+(.)/g, (m, chr) => chr.toUpperCase());
    if(linkData == '#projectMain') {
      item.setAttribute("selected", "true");
    } else {
      item.setAttribute("selected", "false");
    }

    //if(linkData == "#projectMain") item.setAttribute("aria-selected", "true");

    item.innerHTML = this._getText({"type":type, "text": name});

    item.addEventListener("click", (event) => {
      event.preventDefault();

      this._shadow.querySelectorAll('[selected="true"]').forEach( el => {
        el.setAttribute("selected", "false");
      })
      event.target.setAttribute("selected", "true");

      this.toggleItem({ "itemIdSelector":linkData});
    });

    return this.nav.appendChild(item);
  }

_addHeadingWithSubItems({name = "Default", type = "project", subItems = [], itemDivId = -1, linkData = "#"} = {} ){
  let itemHeading = document.createElement("button");
  let hiddenSubNav = document.createElement("nav");
  let navGroup = document.createElement("div");

  navGroup.setAttribute("class", "SubNav")
  navGroup.appendChild(itemHeading);
  navGroup.appendChild(hiddenSubNav);

  // Heading button
  itemHeading.setAttribute("class", `h5 SideNav-heading toggle-subitems-${type}`); // ie. video,image,multi,localization,leaf,state
  itemHeading.innerHTML = this._getText({"text": name, "type": type}); // name ie. Video Type, type video to get correct icon
  itemHeading.setAttribute("selected", "false");

  // SubItems
  if (subItems.length > 0){
    hiddenSubNav.setAttribute("class", `SideNav subitems-${type}`);
    hiddenSubNav.hidden = true;
    for(let obj of subItems){
      let itemId = obj.id; // ie. video type with ID of 62
      let subNavLink = document.createElement("a");
      let subItemText = obj.name;

      subNavLink.setAttribute("class", "SideNav-subItem");
      subNavLink.style.paddingLeft = "44px";

      let itemIdSelector = `#itemDivId-${type}-${itemId}`
      subNavLink.href = itemIdSelector;
      subNavLink.innerHTML = subItemText;

      hiddenSubNav.appendChild(subNavLink);

      // Sub Nav Links
      subNavLink.addEventListener("click", (event) => {
        event.preventDefault();

        this._shadow.querySelectorAll('[selected="true"]').forEach( el => {
          el.setAttribute("selected", "false");
        })
        event.target.setAttribute("selected", "true");
        event.target.parentNode.parentNode.querySelector('button').setAttribute("selected", "true");

        console.log("id for toggle: "+itemIdSelector);

        // @TODO could use type to find dom from array (make array assoc.)
        this.toggleItem({ "itemIdSelector" : itemIdSelector });
      });

    }
  } else {
    console.log("No subitems for heading "+name);
  }

  this.nav.appendChild(navGroup);

  // Heading toggle links
  return this.nav.querySelector(`.toggle-subitems-${type}`).addEventListener(
    "click", (event) => {
      event.preventDefault();

      this._shadow.querySelectorAll('[selected="true"]').forEach( el => {
        el.setAttribute("selected", "false");
      })


      let currentHide = this.toggleSubItemList({ "elClass" : `.subitems-${type}`});
      event.target.setAttribute("selected", currentHide);
    }
  );

}

_getText({type = "", count = 0, text = ""} = {}){
  let icon = "";
  switch(type){
    case "project" :
      icon = this.projectIconSvg();
      break;
    case "media" :
      icon = this.multiIconSvg();
      break;
    case "localization" :
      icon = this.localizationIconSvg();
      break;
    case "leaf" :
      icon = this.leafIconSvg();
      break;
    case "state" :
      icon = this.stateIconSvg();
      break;
    }

    return `${icon} <span class="item-label">${text} ${this._getLabel(count)}</span>`;
  }

  _getLabel(count){
    if(count === 0) return "";
    return `<span class="Label">${count} Attributes</span>`;
  }

  projectIconSvg(){
    return '<svg class="SideNav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><path fill-rule="evenodd" d="M1.75 0A1.75 1.75 0 000 1.75v12.5C0 15.216.784 16 1.75 16h12.5A1.75 1.75 0 0016 14.25V1.75A1.75 1.75 0 0014.25 0H1.75zM1.5 1.75a.25.25 0 01.25-.25h12.5a.25.25 0 01.25.25v12.5a.25.25 0 01-.25.25H1.75a.25.25 0 01-.25-.25V1.75zM11.75 3a.75.75 0 00-.75.75v7.5a.75.75 0 001.5 0v-7.5a.75.75 0 00-.75-.75zm-8.25.75a.75.75 0 011.5 0v5.5a.75.75 0 01-1.5 0v-5.5zM8 3a.75.75 0 00-.75.75v3.5a.75.75 0 001.5 0v-3.5A.75.75 0 008 3z"></path></svg>';
  }

  videoIconSvg(){
    return '<svg class="SideNav-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M15.2 2.09L10 5.72V3c0-.55-.45-1-1-1H1c-.55 0-1 .45-1 1v9c0 .55.45 1 1 1h8c.55 0 1-.45 1-1V9.28l5.2 3.63c.33.23.8 0 .8-.41v-10c0-.41-.47-.64-.8-.41z"/></svg>';
  }

  imageIconSvg(){
    return '<svg class="SideNav-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M15 3H7c0-.55-.45-1-1-1H2c-.55 0-1 .45-1 1-.55 0-1 .45-1 1v9c0 .55.45 1 1 1h14c.55 0 1-.45 1-1V4c0-.55-.45-1-1-1zM6 5H2V4h4v1zm4.5 7C8.56 12 7 10.44 7 8.5S8.56 5 10.5 5 14 6.56 14 8.5 12.44 12 10.5 12zM13 8.5c0 1.38-1.13 2.5-2.5 2.5S8 9.87 8 8.5 9.13 6 10.5 6 13 7.13 13 8.5z"/></svg>';
  }

  multiIconSvg(){
    return '<svg class="SideNav-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 12 16"><path fill-rule="evenodd" d="M6 5h2v2H6V5zm6-.5V14c0 .55-.45 1-1 1H1c-.55 0-1-.45-1-1V2c0-.55.45-1 1-1h7.5L12 4.5zM11 5L8 2H1v11l3-5 2 4 2-2 3 3V5z"/></svg>';
  }

  localizationIconSvg(){
    return '<svg class="SideNav-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="22" y1="12" x2="18" y2="12"></line><line x1="6" y1="12" x2="2" y2="12"></line><line x1="12" y1="6" x2="12" y2="2"></line><line x1="12" y1="22" x2="12" y2="18"></line></svg>';
  }

  leafIconSvg(){
    return '<svg class="SideNav-icon" version="1.1" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 512 512"><title></title><path d="M505.664 67.248c-55.376-41.964-140.592-67.017-227.955-67.017-108.060 0-196.113 37.728-241.58 103.51-21.354 30.895-33.165 67.479-35.104 108.737-1.727 36.737 4.442 77.363 18.342 121.073 47.437-142.192 179.91-253.551 332.633-253.551 0 0-142.913 37.616-232.762 154.096-0.056 0.069-1.247 1.545-3.307 4.349-18.040 24.139-33.769 51.581-45.539 82.664-19.935 47.415-38.392 112.474-38.392 190.891h64c0 0-9.715-61.111 7.18-131.395 27.945 3.778 52.929 5.653 75.426 5.653 58.839 0 100.685-12.73 131.694-40.062 27.784-24.489 43.099-57.393 59.312-92.228 24.762-53.204 52.827-113.505 134.327-160.076 4.665-2.666 7.681-7.496 8.028-12.858s-2.020-10.54-6.303-13.786z"></path></svg>';
  }

  stateIconSvg(){
    return '<svg class="SideNav-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path><line x1="4" y1="22" x2="4" y2="15"></line></svg>';
  }




  /* Check if side nav name needs to be updated.... @TODO */
  /*static get observedAttributes() {
    return ["_data"].concat(TatorPage.observedAttributes);
  }
  attributeChangedCallback(name, oldValue, newValue) {
    TatorPage.prototype.attributeChangedCallback.call(this, name, oldValue, newValue);
    switch (name) {
      case "_data":
        this._init();
        break;
    }
  };*/

  toggleItem({ itemIdSelector = ``} = {}){
    let targetEl = null;
    let typeDomArray = this._getDomArray();

    for(let dom of typeDomArray){
      // Hide all other item boxes
      dom.querySelectorAll('.item-box').forEach( (el) => {
        //if(!dom.querySelector(".changed")){
          el.hidden = true;
          // Find and show our target
          targetEl = dom.querySelector( itemIdSelector );
          if(targetEl) targetEl.hidden = false;
        //} else {
        //  this._modalError("You have unsaved changes", "Please save or discard changes to "+dom.querySelector(".changed h2"));
        //}
      } );
    }
  };

  // _modalError(text, message){
  //   let textNode = document.createTextNode(" "+text);
  //   this.modal._titleDiv.innerHTML = "";
  //   this.modal._titleDiv.append( document.createElement("modal-warning") );
  //   this.modal._titleDiv.append(textNode);
  //   this.modal._main.innerHTML = message;
  //
  //   return this.modal.setAttribute("is-open", "true")
  // }

  toggleSubItemList({ elClass = ``} = {}){
    //console.log(elClass);
    let targetEl = this.nav.querySelector( elClass );
    let targetElHidden = targetEl.hidden;

    targetEl.hidden = !targetElHidden

    return targetElHidden;
  };

  setProjectDom( ref ){
    return this.projectDom = ref;
  }
  setMediaDom ( ref ){
    return this.mediaDom = ref;
  }
  setLocalizationDom( ref ){
    return this.localizationDom = ref;
  }
  setLeafDom( ref ){
    return this.leafDom = ref;
  }
  setStateDom( ref ){
    return this.stateDom = ref;
  }

  _getDomArray(){
    return [
      this.projectDom,
      this.mediaDom,
      this.localizationDom,
      this.leafDom,
      this.stateDom
    ];
  }

}

customElements.define("settings-nav", SettingsNav);