/* Receives the coordinates captured in the LavaFlow Mapper map (folium iframe)
   and keeps them in a global array that a Dash clientside callback polls. */
window.__lavaflow = window.__lavaflow || {points: [], active: false};

window.addEventListener('message', function (ev) {
    var d = ev.data || {};
    if (!d || d.source !== 'lavaflow-capture') return;
    if (d.action === 'add') {
        window.__lavaflow.points.push({lat: d.lat, lon: d.lon, index: d.index});
    } else if (d.action === 'on' || d.action === 'off') {
        window.__lavaflow.active = (d.action === 'on');
    }
});

window.__lavaflowClear = function () {
    window.__lavaflow.points = [];
    document.querySelectorAll('iframe.lf-map-frame').forEach(function (f) {
        try { f.contentWindow.postMessage({source: 'lavaflow-capture-parent', action: 'clear'}, '*'); } catch (e) {}
    });
};
