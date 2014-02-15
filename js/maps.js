var STATIC_URL = $('body').data('static-url');

var ShrinkMapControl = L.Control.extend({
    options: {
        position: 'bottomleft'
    },

    onAdd: function (map) {
        // create the control container with a particular class name
        var container = L.DomUtil.create('div', 'shrinkControl');
        container.innerHTML = 'Shrink map';
        L.DomEvent.addListener(container, 'click', this.onClick, this);

        return container;
    },

    onClick: function (e) {
        this._map.shrink();
        L.DomEvent.stop(e);
    }
});


L.Icon.Default.imagePath = STATIC_URL + 'djangopeople/leaflet/images/';
var DJIcon = L.Icon.Default.extend({
    options: {
        iconUrl: STATIC_URL + 'djangopeople/img/green-bubble.png'
    }
});

var DJMarker = L.Marker.extend({

    options: {
        icon: new DJIcon()
    },

    initialize: function (person) {
        lat = person[0];
        lng = person[1];
        var latlng = new L.LatLng(lat, lng);
        L.Marker.prototype.initialize.call(this, latlng);
        this.person = person;
        this.name = person[2];
        this.username = person[3];
        this.location = this.person[4];
        this.photo = person[5];
        this.iso_code = person[6];
        this.initPopup();
    },

    initPopup: function () {
        var container = L.DomUtil.create('ul', 'detailsList'),
            li = L.DomUtil.create('li', '', container),
            img = L.DomUtil.create('img', '', li);
        img.src = this.photo;
        var h3 = L.DomUtil.create('h3', '', li),
            a = L.DomUtil.create('a', '', h3);
        a.href = '/' + this.username + '/';
        a.innerHTML = this.name;
        var p = L.DomUtil.create('p', 'meta', li);
        a = L.DomUtil.create('a', 'nobg', p);
        a.href = '/' + this.iso_code + '/';
        img = L.DomUtil.create('img', '', a);
        img.src = STATIC_URL + 'djangopeople/img/flags/' + this.iso_code + '.gif';
        a.innerHTML = a.innerHTML + " " + this.location;
        p = L.DomUtil.create('p', 'meta', li);
        a = L.DomUtil.create('a', '', p);
        a.innerHTML = "Zoom to point";
        L.DomEvent.on(a, "click", L.DomEvent.stop)
                  .on(a, "click", this.bringToCenter, this);
        this.bindPopup(container);
    },

    bringToCenter: function (e) {
        var latlng;
        if (e && e.latlng) {
            latlng = e.latlng;
        }
        else {
            latlng = this.getLatLng();
        }
        this._map.panTo(latlng);
        this._map.setZoom(8);
    }

});

var DJMap = L.Map.extend({
    /* Plots people on the maps and adds an info window to it
     * which becomes visible when you click the marker
     */
    plotPeople: function (people) {
        var bounds = new L.LatLngBounds(),
            map = this;
        $.each(people, function(index, person) {
            var marker = new DJMarker(person);
            bounds.extend(marker.getLatLng());
            marker.addTo(map);
        });
        this.fitBounds(bounds, {reset: true});
        return bounds;
    },

    unShrink: function () {
        var map = this;
        // Unbind event so user can actually interact with map
        map.off('click', this.unShrink);

        $('#map').css({'cursor': ''}).attr('title', '');
        $('#map').animate({
            height: '25em',
            opacity: 1.0
        }, 500, 'swing', function() {
            map.invalidateSize();
            if (map.shrinkControl) {
                map.shrinkControl.addTo(map);
            }
        });
    },

    shrink: function (latlng) {
        latlng = latlng || this.getCenter();
        this.panTo(latlng);
        if (this.shrinkControl) {
            this.shrinkControl.removeFrom(this);
        }
        var map = this;

        $('#map').css({'cursor': 'pointer'}).attr(
            'title', 'Activate larger map'
        );
        $('#map').animate({
            height: '7em',
            opacity: 0.6
        }, 500, 'swing', function() {
            map.invalidateSize();
        });

        /* Map enlarges and becomes active when you click on it */
        this.on('click', this.unShrink);
    },

    shrinkable: function (latlng) {
        this.shrinkControl = new ShrinkMapControl().addTo(this);

        // Marker for the current profile, not clickable
        var icon = new DJIcon({iconUrl: STATIC_URL + 'djangopeople/img/gray-bubble.png'});
        new L.Marker(latlng, {icon: icon}).addTo(this)._bringToFront();
        this.shrink(latlng);
    }
});
