const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/main/webapp/js/diagramly/ControlProfiles.js'), 'utf8');

function setup(saved, settingsEnabled = true) {
  const calls = [];
  const rb = {first: null, cancelled: false,
    cancel() {this.reset();}, reset() {this.first = null;},
    isForceRubberbandEvent(me) {return !!me.getEvent().altKey;},
    mouseUp() {calls.push('select'); this.reset();}};
  const pan = {reset() {}, isForcePanningEvent() {return false;},
    mouseMove() {calls.push('pan');}, mouseUp() {this.reset();}};
  const graph = {container: {}, tolerance: 4, freehand: null,
    isEditing() {return this.editing || false;}, getRubberband() {return rb;},
    panningHandler: pan, isZoomWheelEvent(e) {return !!e.altKey;},
    popupMenuHandler: {isPopupTrigger(me) {return me.getEvent().button === 2;}},
    zoomIn() {calls.push('in');}, zoomOut() {calls.push('out');},
    zoomToRect(rect) {calls.push(['rect', rect.x, rect.y, rect.width, rect.height]);}};
  const extras = {funct() {calls.push('original-menu');}};
  function EditorUi() {this.editor = {graph}; this.dialogs = []; this.menus = {get() {return extras;}};
    this.keyHandler = {getFunction() {return 'default-key';}};
    this.actions = {get() {return {funct() {calls.push('fit');}};}};}
  EditorUi.prototype.init = function() {};
  EditorUi.prototype.destroy = function() {calls.push('destroy');};
  const settings = {settings: {controlProfile: saved}, save() {calls.push('save');}};
  const context = {EditorUi, Editor: {isSettingsEnabled() {return settingsEnabled;}, checkmarkImage: 'check'}, mxSettings: settings,
    mxPoint: function(x,y) {this.x=x;this.y=y;},
    mxRectangle: function(x,y,width,height) {Object.assign(this,{x,y,width,height});},
    mxUtils: {convertPoint(_,x,y) {return {x,y};}},
    mxResources: {get(_,__,fallback) {return fallback;}},
    mxEvent: {isControlDown: e=>!!e.ctrlKey,isShiftDown:e=>!!e.shiftKey,isAltDown:e=>!!e.altKey,isMetaDown:e=>!!e.metaKey,
      isLeftMouseButton:e=>e.button===0,isRightMouseButton:e=>e.button===2,
      addListener(_,name,fn) {calls.push(['listen',name]);}, removeListener(){calls.push('unlisten');}, consume(e){e.consumed=true;}}};
  vm.runInNewContext(source, context);
  const ui = new EditorUi();ui.init();
  const event = (options={}) => {
    const evt={button:0,x:20,y:30,...options};
    return {getEvent:()=>evt,getX:()=>evt.x,getY:()=>evt.y,consume(){evt.consumed=true;}};
  };
  const nav = (options={}) => event({ctrlKey:true,shiftKey:true,...options});
  return {ui,graph,rb,pan,settings,calls,event,nav,extras};
}

test('draw.io remains default and its original handlers are delegated', () => {
  const s=setup();
  assert.equal(s.ui.controlProfile,'drawio');
  assert.equal(s.graph.isZoomWheelEvent({altKey:true}),true);
  assert.equal(s.graph.isZoomWheelEvent({ctrlKey:true}),false);
  assert.equal(s.rb.isForceRubberbandEvent(s.nav()),false);
  s.rb.mouseUp(null,s.event());
  assert.ok(s.calls.includes('select'));
});
test('Visio wheel policy, persistence, restore and settings-disabled behavior', () => {
  const s=setup();s.ui.setControlProfile('visio');
  assert.equal(s.settings.settings.controlProfile,'visio');
  assert.equal(s.graph.isZoomWheelEvent({}),false);
  assert.equal(s.graph.isZoomWheelEvent({ctrlKey:true}),true);
  assert.equal(s.graph.isZoomWheelEvent({altKey:true}),false);
  assert.equal(setup('visio').ui.controlProfile,'visio');
  assert.equal(setup('visio',false).ui.controlProfile,'drawio');
  s.ui.setControlProfile('drawio');assert.equal(s.graph.isZoomWheelEvent({altKey:true}),true);
  s.ui.setControlProfile('unknown');assert.equal(s.ui.controlProfile,'drawio');
});
test('Ctrl+Shift left click zooms; dragging in either direction fits a rectangle', () => {
  const s=setup('visio');
  assert.equal(s.pan.isForcePanningEvent(s.nav()),false);
  assert.equal(s.rb.isForceRubberbandEvent(s.nav()),true);
  s.rb.first={x:20,y:30};s.rb.mouseUp(null,s.nav());
  assert.ok(s.calls.includes('in'));assert.equal(s.rb.first,null);
  s.rb.isForceRubberbandEvent(s.nav());s.rb.first={x:120,y:130};
  s.rb.mouseUp(null,s.nav({x:20,y:30,ctrlKey:false,shiftKey:false}));
  assert.ok(s.calls.some(c=>Array.isArray(c)&&c[0]==='rect'&&c[1]===20&&c[2]===30&&c[3]===100&&c[4]===100));
  assert.ok(!s.calls.includes('select'));
});
test('right click zooms out, right drag pans without zoom even if it returns to start', () => {
  const s=setup('visio');const me=s.nav({button:2});
  assert.equal(s.pan.isForcePanningEvent(me),true);
  assert.equal(s.graph.popupMenuHandler.isPopupTrigger(me),false);
  s.pan.mouseUp(null,me);assert.equal(s.calls.filter(c=>c==='out').length,1);
  s.pan.isForcePanningEvent(me);
  s.pan.mouseMove(null,s.nav({button:2,x:90}));s.pan.mouseUp(null,me);
  assert.equal(s.calls.filter(c=>c==='out').length,1);
  assert.equal(s.graph.popupMenuHandler.isPopupTrigger(s.event({button:2})),true);
});
test('editing, dialogs, freehand and Alt combinations retain native behavior', () => {
  const s=setup('visio');
  s.graph.editing=true;assert.equal(s.rb.isForceRubberbandEvent(s.nav()),false);
  s.graph.editing=false;s.ui.dialogs=[{}];assert.equal(s.pan.isForcePanningEvent(s.nav({button:2})),false);
  s.ui.dialogs=[];s.graph.freehand={isActive:()=>true};assert.equal(s.rb.isForceRubberbandEvent(s.nav()),false);
  s.graph.freehand=null;
  assert.equal(s.rb.isForceRubberbandEvent(s.nav({altKey:true})),true); // native Alt marquee/scissors
  assert.equal(typeof s.ui.keyHandler.getFunction(s.nav({keyCode:87}).getEvent()) === 'function',true);
  s.ui.keyHandler.getFunction(s.nav({keyCode:87}).getEvent())();assert.ok(s.calls.includes('fit'));
});
test('cancellation and profile changes cannot complete an old navigation gesture', () => {
  const s=setup('visio');s.rb.isForceRubberbandEvent(s.nav());s.rb.first={x:20,y:30};
  s.rb.reset();s.rb.first={x:20,y:30};s.rb.mouseUp(null,s.event());
  assert.ok(!s.calls.includes('in'));
  s.pan.isForcePanningEvent(s.nav({button:2}));s.pan.reset();s.pan.mouseUp(null,s.nav({button:2}));
  assert.ok(!s.calls.includes('out'));
  s.ui.setControlProfile('drawio');s.rb.mouseUp(null,s.nav());assert.ok(!s.calls.includes('in'));
});
test('menu includes both profiles, reflects current choice, and cleanup removes listener', () => {
  const s=setup('visio');const items=[];
  const menu={addSeparator(){},addItem(label,icon,fn,parent){const item={label,fn,parent};items.push(item);return item;},addCheckmark(item){item.checked=true;}};
  s.extras.funct(menu,null);
  assert.equal(items.find(i=>i.label==='Visio').checked,true);
  items.find(i=>i.label==='draw.io').fn();assert.equal(s.ui.controlProfile,'drawio');
  s.ui.destroy();assert.ok(s.calls.includes('unlisten'));assert.ok(s.calls.includes('destroy'));
});
