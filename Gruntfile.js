module.exports = function(grunt) {
    grunt.initConfig({
        pkg: grunt.file.readJSON('package.json'),

        concat: {
            dist: {
                src: [
                    'vendor/jquery-1.11.0.min.js',
                    'vendor/jquery.color.js',
                    'vendor/leaflet.js',
                    'js/maps.js',
                    'js/djangopeople.js',
                ],
                dest: 'djangopeople/djangopeople/static/djangopeople/js/djangopeople.js',
            },
        },

        uglify: {
            build: {
                src: 'djangopeople/djangopeople/static/djangopeople/js/djangopeople.js',
                dest: 'djangopeople/djangopeople/static/djangopeople/js/djangopeople.min.js',
            },
        },

        watch: {
            scripts: {
                files: [
                    'Gruntfile.js',
                    'js/**/*.js',
                    'vendor/**/*.js',
                ],
                tasks: ['concat'],
                options: {
                    spawn: false,
                },
            },
        },
    });

    grunt.loadNpmTasks('grunt-contrib-concat');
    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-contrib-watch');

    grunt.registerTask('default', ['concat', 'uglify']);
};
