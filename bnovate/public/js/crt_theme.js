/* crt_theme.js. (c) 2026, bNovate.
 *
 * Loads the amber CRT theme (css/crt_theme.css) for the users who chose it: field "Theme" of the User (custom field bn_theme,
 * in My Settings). The desk only: this is included by hooks.py (app_include_js), never on the website, print formats or PDFs.
 *
 * To try it out without changing the setting, from the console of the browser:
 *     bnovate.crt.on()      bnovate.crt.off()
 ****************************************************/

(function () {
    const THEME = 'Amber CRT';              // value of the Theme field of the User
    const STYLESHEET = '/assets/bnovate/css/crt_theme.css';

    window.bnovate = window.bnovate || {};

    // Duotone ramp from the amber phosphor (dark pixels: text) to the dark screen (white pixels: page).
    // Stops are at 0, 25, 50, 75 and 100% of the luminance of the original.
    //          0%     25%    50%    75%    100%
    const RAMP = {
        r: [1.000, 1.000, 0.820, 0.400, 0.050],
        g: [0.860, 0.760, 0.520, 0.250, 0.030],
        b: [0.480, 0.060, 0.000, 0.000, 0.010],
    };

    function add_filter() {
        if (document.getElementById('bn-crt-svg')) return;
        const table = channel => RAMP[channel].join(' ');
        const holder = document.createElement('div');
        holder.innerHTML = `
            <svg id="bn-crt-svg" width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
                <filter id="bn-crt" color-interpolation-filters="sRGB" x="0" y="0" width="100%" height="100%">
                    <feColorMatrix type="saturate" values="0"/>
                    <feComponentTransfer>
                        <feFuncR type="table" tableValues="${table('r')}"/>
                        <feFuncG type="table" tableValues="${table('g')}"/>
                        <feFuncB type="table" tableValues="${table('b')}"/>
                    </feComponentTransfer>
                </filter>
            </svg>`;
        document.body.appendChild(holder.firstElementChild);
    }

    function add_stylesheet(done) {
        if (document.getElementById('bn-crt-css')) return done();
        const link = document.createElement('link');
        link.id = 'bn-crt-css';
        link.rel = 'stylesheet';
        link.href = STYLESHEET + '?v=' + (window.bnovate_crt_version || '1');
        link.onload = done;
        document.head.appendChild(link);
    }

    function switch_on(boot) {
        add_filter();
        add_stylesheet(() => {
            const html = document.documentElement;
            html.classList.add('bn-crt');
            if (boot) {
                html.classList.add('bn-crt-boot');
                setTimeout(() => html.classList.remove('bn-crt-boot'), 1000);
            }
        });
    }

    function switch_off() {
        document.documentElement.classList.remove('bn-crt', 'bn-crt-boot');
    }

    bnovate.crt = {
        on() { switch_on(true); },
        off() { switch_off(); },
    };

    // The setting of the user. One small request when the desk opens.
    async function apply_user_setting() {
        if (!window.frappe || !frappe.db || !frappe.session || frappe.session.user === 'Guest') return;
        const resp = await frappe.db.get_value('User', frappe.session.user, 'bn_theme');
        if (resp && resp.message && resp.message.bn_theme === THEME) {
            switch_on(true);
        }
    }

    // 'startup' is triggered by the desk once the session is known (the scripts are loaded before that)
    $(document).on('startup', apply_user_setting);

    // Saving the setting takes effect at once, without a reload
    if (window.frappe && frappe.ui && frappe.ui.form) {
        frappe.ui.form.on('User', {
            after_save(frm) {
                if (frm.doc.name !== frappe.session.user) return;
                frm.doc.bn_theme === THEME ? switch_on(true) : switch_off();
            },
        });
    }
})();
