function getPersonPopupContent(person) {
    var lat = person[0];
    var lon = person[1];
    var name = person[2];
    var username = person[3];
    var location_description = person[4];
    var photo = person[5];
    var iso_code = person[6];
    var html =  '<ul class="detailsList">' + 
        '<li>' + 
        '<img src="' + photo + '" alt="' + name + '" class="main">' + 
        '<h3><a href="/' + username + '/">' + name + '</a></h3>' + 
        '<p class="meta"><a href="/' + iso_code + '/" class="nobg">' + 
        '<img src="' + STATIC_URL + 'djangopeople/img/flags/' + iso_code + '.gif"></a> ' + 
        location_description + '</p>' + 
        '<p class="meta"><a href="#" onclick="zoomOn(' + lat + ', ' + lon + '); return false;">Zoom to point</a></p>' +
        '</li>';
    return html;
}

function zoomOn(lat, lon) {
    MAP.setCenter(new L.LatLng(lat, lon));
    MAP.setZoom(12);
}

/* Plots people on the maps and adds an info window to it
 * which becomes visible when you click the marker
 */
function plotPeopleOnMap(people, map) {
    var bounds = new L.LatLngBounds();
    $.each(people, function(index, person) {
        var marker = getPersonMarker(person);
        bounds.extend(marker.getLatLng());
        marker.addTo(map);
    });
    map.fitBounds(bounds);
    return bounds;
}

// Creates a Marker object for a person
function getPersonMarker(person) {
    var lat = person[0];
    var lon = person[1];
    var point = new L.LatLng(lat, lon);
    // custom marker options removed for now
    var marker = new L.Marker(point, {
        icon: greenIconImage(),
    });
    var info = getPersonPopupContent(person);
    marker.bindPopup(info)

    return marker;
}

function greenIconImage() {
    var greenIcon = L.icon({
        iconUrl: STATIC_URL + 'djangopeople/img/green-bubble.png',
        shadowUrl: STATIC_URL + 'djangopeople/img/green-bubble-shadow.png',
        iconSize:     [32, 32], // size of the icon
        shadowSize:   [32, 32], // size of the shadow
        iconAnchor:   [16, 32], // point of the icon which will correspond to marker's location
        shadowAnchor: [10, 32],  // the same for the shadow
        popupAnchor:  [0, -32] // point from which the popup should open relative to the iconAnchor
    });
    return greenIcon;
}
