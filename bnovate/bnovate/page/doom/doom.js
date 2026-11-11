frappe.pages['doom'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'You have arrived.',
        single_column: true
    });
    let form = new frappe.ui.FieldGroup({
        fields: [{
            label: 'Container',
            fieldname: 'container',
            fieldtype: 'HTML',
            options: '<div id="doom-body" style="height: 600px"></div>',
        }],
        body: page.body
    });

    form.make();
    page.form = form;
    const container = document.getElementById('doom-body');
    container.innerHTML = frappe.render_template("doom");

    var preview = null;
    var doomCanvas = null;
    var fullscreenButton = null;
    const assetRoot = "/assets/bnovate/js/lib/doom/"

    // data is almost 100MB, keep out of this repo.
    const dataUrl = "https://ustymukhman.github.io/WebDOOM/public/doom1.data";

    window.Module = {
        monitorRunDependencies: function (toLoad) {
            this.dependencies = Math.max(this.dependencies, toLoad);
        },

        inFullscreen: false,
        dependencies: 0,

        setStatus: null,
        progress: null,

        loader: null,
        canvas: null,

        // Everything is served from our assets, except the data package
        locateFile: function (path) {
            return path.endsWith('.data') ? dataUrl : assetRoot + path;
        }
    };

    function getCanvas() {
        doomCanvas.addEventListener('webglcontextlost', function (event) {
            alert('WebGL context lost. You need to reload the page.');
            event.preventDefault();
        }, false);

        doomCanvas.addEventListener('contextmenu', function (event) {
            event.preventDefault();
        });

        fullscreenButton.addEventListener('click', function () {
            Module.requestFullscreen(true, false);
        });

        return doomCanvas;
    }

    function getStatus(status) {
        var loading = status.match(/([^(]+)\((\d+(\.\d+)?)\/(\d+)\)/);

        if (loading) {
            var progress = loading[2] / loading[4] * 100;
            Module.progress.innerHTML = progress.toFixed(1) + '%';

            if (progress === 100) {
                setTimeout(function () {
                    fullscreenButton.classList.add('visible');
                    Module.loader.classList.add('completed');
                    doomCanvas.classList.add('ready');
                }, 500);

                setTimeout(function () {
                    Module.canvas.dispatchEvent(new Event('mousedown'));
                }, 2000);
            }
        }
    }

    let count = 0;
    function onPointerLockChange() {
        // if (count > 0) {
        //     return;
        // }
        Module.inFullscreen = !Module.inFullscreen;
        if (!Module.inFullscreen) {
            doomCanvas.classList.remove('centered');
        } else {
            doomCanvas.classList.add('centered');
        }

        // document.exitPointerLock();
        // count += 1;
    }

    function onGameClick(game) {
        var doomScript = document.createElement('script');
        document.body.appendChild(doomScript);
        doomScript.type = 'text/javascript';

        preview.classList.add('hidden');
        doomScript.src = assetRoot + game + '.js';
    }

    var games = document.getElementsByClassName('doom');
    preview = document.getElementById('preview');

    document.exitPointerLock = document.exitPointerLock || document.mozExitPointerLock || document.webkitExitPointerLock;
    document.exitFullscreen = document.exitFullscreen || document.mozCancelFullScreen || document.webkitCancelFullScreen;

    document.addEventListener('mozpointerlockchange', onPointerLockChange, false);
    document.addEventListener('pointerlockchange', onPointerLockChange, false);

    games[0].addEventListener('click', onGameClick.bind(null, 'doom1'));
    // games[1].addEventListener('click', onGameClick.bind(null, 'doom2'));

    fullscreenButton = document.getElementById('fullscreen');
    Module.progress = document.getElementById('progress');
    Module.loader = document.getElementById('loader');
    doomCanvas = document.getElementById('doom');

    Module.setStatus = getStatus;
    Module.canvas = getCanvas();
}