/*
Warehouse Wars
--------------

A little point-and-shoot easter egg, played with a handheld barcode/QR
reader. Enemies are crates marching Space-Invaders-style across the screen,
each carrying a QR code that encodes a REAL Serial No from the database.
"Shooting" an enemy means literally scanning its code with a real reader -
the reader behaves as a keyboard (it types the code, then Enter or Tab), so
all we do is listen for keystrokes on the whole page, buffer them, and on
Enter/Tab check the buffered text against the codes of enemies still alive.

No mouse aiming, no on-screen typing required - point the scanner at the
monitor and pull the trigger.
*/

frappe.pages['warehouse-wars'].on_page_load = function (wrapper) {
	// frappe.require is callback-based (no promise support in this version),
	// wrap it so build_enemies() can safely await QRCode being loaded before
	// first use, rather than relying on it having loaded in time by chance.
	const qrcode_ready = new Promise(resolve => frappe.require("/assets/bnovate/js/lib/qrcode.min.js", resolve));

	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Warehouse Wars',
		single_column: true,
	});

	// Levels: one background image + a few knobs per level. Add more entries
	// here as new photos arrive - level_index cycles through this list,
	// looping back to the start (with enemies/speed still scaling up) once
	// it runs out, so the game never just "ends" when backgrounds do.
	const LEVELS = [
		{ background: "/assets/bnovate/img/warehouse_wars/level1.jpg", enemy_count: 16, speed: 1.0 },
	];

	const CONFIG = {
		width: 940,
		height: 600,
		cols: 6,
		enemy_size: 64,
		h_gap: 18,
		v_gap: 56,
		margin_top: 70,
		margin_side: 40,
		step_down: 22,
		max_descent: 360, // formation reaching this far down costs a life
		start_lives: 3,
		scan_reset_ms: 500, // buffered keystrokes older than this are dropped
	};

	const state = {
		phase: 'intro', // intro | playing | level_clear | game_over
		level_index: 0,
		score: 0,
		lives: CONFIG.start_lives,
		enemies: [], // {code, el, alive, row, col}
		formation_x: 0,
		formation_y: 0,
		direction: 1,
		speed: 1,
		raf_id: null,
		scan_buffer: "",
		last_key_time: 0,
	};

	inject_styles();

	const root = $(`
		<div class="wawa-stage">
			<div class="wawa-screen">
				<div class="wawa-hud">
					<span class="wawa-hud-item">${__('Score')}: <b class="wawa-score">0</b></span>
					<span class="wawa-hud-item wawa-lives"></span>
					<span class="wawa-hud-item">${__('Level')} <b class="wawa-level">1</b></span>
				</div>
				<div class="wawa-formation"></div>
				<div class="wawa-player">▲</div>
				<div class="wawa-overlay wawa-overlay-visible">
					<div class="wawa-overlay-inner">
						<h2>${__('WAREHOUSE WARS')}</h2>
						<p>${__('Inventory invaders have infested the warehouse!')}<br>
						${__("Scan a crate's code with your barcode reader to destroy it.")}</p>
						<button class="btn btn-primary btn-sm wawa-start-btn">${__('Start')}</button>
					</div>
				</div>
			</div>
		</div>
	`).appendTo(page.body);

	const $screen = root.find('.wawa-screen');
	const $formation = root.find('.wawa-formation');
	const $overlay = root.find('.wawa-overlay');
	const $score = root.find('.wawa-score');
	const $level = root.find('.wawa-level');
	const $lives = root.find('.wawa-lives');

	$screen.css({ width: CONFIG.width + 'px', height: CONFIG.height + 'px' });

	root.find('.wawa-start-btn').on('click', () => start_level());

	// --- Input: the whole point of the game. A barcode reader is just a very
	// fast keyboard - we don't need focus on any particular field, just
	// listen globally, buffer printable characters, and act on Enter/Tab.
	// Capture phase + stopPropagation so a scanned code's letters can't
	// trigger Frappe's own global keyboard shortcuts along the way.
	document.addEventListener('keydown', on_keydown, true);

	function on_keydown(e) {
		if (state.phase !== 'playing') return;

		const now = Date.now();
		if (now - state.last_key_time > CONFIG.scan_reset_ms) {
			state.scan_buffer = "";
		}
		state.last_key_time = now;

		// Enter/Tab used to be required to submit a scan. Some readers still
		// send one after the code, but matching is now live (see
		// check_scan_buffer below), so just swallow it rather than require it.
		if (e.key === 'Enter' || e.key === 'Tab') {
			e.preventDefault();
			e.stopPropagation();
			return;
		}

		if (e.key.length === 1) {
			state.scan_buffer += e.key;
			e.stopPropagation();
			check_scan_buffer();
		}
	}

	// Checks the buffered keystrokes against alive enemies after every
	// character, instead of waiting for a terminator key. An exact match
	// kills that enemy immediately; if no alive code could still complete
	// the current buffer (wrong code, typo, stray keystroke...) it can never
	// become a match, so flash a miss right away and reset.
	function check_scan_buffer() {
		let buffer = state.scan_buffer.toUpperCase();
		let alive = state.enemies.filter(en => en.alive);

		let enemy = alive.find(en => en.code.toUpperCase() === buffer);
		if (enemy) {
			state.scan_buffer = "";
			kill_enemy(enemy);
			return;
		}

		let could_still_match = alive.some(en => en.code.toUpperCase().startsWith(buffer));
		if (!could_still_match) {
			state.scan_buffer = "";
			miss_feedback();
		}
	}

	async function start_level() {
		$overlay.removeClass('wawa-overlay-visible');
		let level = LEVELS[state.level_index % LEVELS.length];
		// Every lap through the level list, ramp up difficulty a bit so it
		// doesn't just loop identically forever once photos run out.
		let lap = Math.floor(state.level_index / LEVELS.length);
		$screen.css('background-image', `url(${level.background})`);
		$level.text(state.level_index + 1);

		let count = level.enemy_count + lap * 4;
		state.speed = level.speed + lap * 0.3;
		state.direction = 1;
		state.formation_x = 0;
		state.formation_y = 0;

		await build_enemies(count);
		state.phase = 'playing';
		run_loop();
	}

	async function build_enemies(count) {
		$formation.empty().css('transform', 'translate(0px, 0px)');
		state.enemies = [];

		await qrcode_ready;

		let r = await frappe.call({
			method: 'bnovate.bnovate.page.warehouse_wars.warehouse_wars.get_enemies',
			args: { count },
		});
		let codes = r.message || [];

		let cols = CONFIG.cols;
		codes.forEach((code, i) => {
			let row = Math.floor(i / cols);
			let col = i % cols;
			let x = CONFIG.margin_side + col * (CONFIG.enemy_size + CONFIG.h_gap);
			let y = CONFIG.margin_top + row * (CONFIG.enemy_size + CONFIG.v_gap);

			let $el = $(`
				<div class="wawa-enemy" style="left:${x}px; top:${y}px; width:${CONFIG.enemy_size}px;">
					<div class="wawa-enemy-badge">👾</div>
					<div class="wawa-enemy-qr"></div>
					<div class="wawa-enemy-code">${esc(code)}</div>
				</div>
			`).appendTo($formation);

			new QRCode($el.find('.wawa-enemy-qr')[0], {
				text: code,
				width: CONFIG.enemy_size,
				height: CONFIG.enemy_size,
				correctLevel: QRCode.CorrectLevel.L,
			});

			state.enemies.push({ code, el: $el, alive: true, row, col });
		});
	}

	function run_loop() {
		cancel_loop();
		function tick() {
			if (state.phase !== 'playing') return;
			step_formation();
			state.raf_id = requestAnimationFrame(tick);
		}
		state.raf_id = requestAnimationFrame(tick);
	}

	function cancel_loop() {
		if (state.raf_id) {
			cancelAnimationFrame(state.raf_id);
			state.raf_id = null;
		}
	}

	function step_formation() {
		let alive_cols = state.enemies.filter(e => e.alive).map(e => e.col);
		if (!alive_cols.length) return;
		let min_col = Math.min(...alive_cols);
		let max_col = Math.max(...alive_cols);
		let left_edge = CONFIG.margin_side + min_col * (CONFIG.enemy_size + CONFIG.h_gap) + state.formation_x;
		let right_edge = CONFIG.margin_side + (max_col + 1) * (CONFIG.enemy_size + CONFIG.h_gap) + state.formation_x;

		state.formation_x += state.speed * state.direction;

		if (right_edge >= CONFIG.width - 4 || left_edge <= 4) {
			state.direction *= -1;
			state.formation_y += CONFIG.step_down;
		}

		$formation.css('transform', `translate(${state.formation_x}px, ${state.formation_y}px)`);

		if (state.formation_y >= CONFIG.max_descent) {
			lose_life();
		}
	}

	function kill_enemy(enemy) {
		enemy.alive = false;
		state.score += 10;
		$score.text(state.score);
		fire_laser(enemy);
		enemy.el.addClass('wawa-enemy-dead');
		setTimeout(() => enemy.el.remove(), 400);

		if (state.enemies.every(e => !e.alive)) {
			level_clear();
		}
	}

	function fire_laser(enemy) {
		let target = enemy.el[0].getBoundingClientRect();
		let screen_rect = $screen[0].getBoundingClientRect();
		let x = target.left - screen_rect.left + target.width / 2;
		let y = target.top - screen_rect.top + target.height / 2;
		let player = root.find('.wawa-player')[0].getBoundingClientRect();
		let px = player.left - screen_rect.left + player.width / 2;
		let py = player.top - screen_rect.top;

		let length = Math.hypot(x - px, y - py);
		let angle = Math.atan2(y - py, x - px) * 180 / Math.PI;

		$(`<div class="wawa-laser" style="left:${px}px; top:${py}px; width:${length}px; transform: rotate(${angle}deg);"></div>`)
			.appendTo($screen)
			.each(function () {
				let el = this;
				setTimeout(() => el.remove(), 180);
			});
	}

	function miss_feedback() {
		$screen.addClass('wawa-miss-flash');
		setTimeout(() => $screen.removeClass('wawa-miss-flash'), 150);
	}

	function lose_life() {
		state.lives -= 1;
		render_lives();
		if (state.lives <= 0) {
			game_over();
		} else {
			cancel_loop();
			build_enemies(state.enemies.length || LEVELS[state.level_index % LEVELS.length].enemy_count).then(() => {
				state.formation_x = 0;
				state.formation_y = 0;
				state.direction = 1;
				run_loop();
			});
		}
	}

	function level_clear() {
		cancel_loop();
		state.phase = 'level_clear';
		state.level_index += 1;
		show_overlay(
			__('LEVEL CLEAR!'),
			__('Score: {0}', [state.score]),
			__('Next Level'),
			() => start_level()
		);
	}

	function game_over() {
		cancel_loop();
		state.phase = 'game_over';
		show_overlay(
			__('GAME OVER'),
			__('Final score: {0}', [state.score]),
			__('Play Again'),
			() => {
				state.score = 0;
				state.lives = CONFIG.start_lives;
				state.level_index = 0;
				$score.text(0);
				render_lives();
				start_level();
			}
		);
	}

	function show_overlay(title, message, button_label, on_click) {
		$overlay.html(`
			<div class="wawa-overlay-inner">
				<h2>${title}</h2>
				<p>${message}</p>
				<button class="btn btn-primary btn-sm wawa-overlay-btn">${button_label}</button>
			</div>
		`);
		$overlay.find('.wawa-overlay-btn').on('click', on_click);
		$overlay.addClass('wawa-overlay-visible');
	}

	function render_lives() {
		$lives.html(Array(Math.max(state.lives, 0)).fill('▲').join(' '));
	}
	render_lives();

	function esc(str) {
		let div = document.createElement('div');
		div.textContent = str;
		return div.innerHTML;
	}

	function inject_styles() {
		if (document.getElementById('wawa-styles')) return;
		let style = document.createElement('style');
		style.id = 'wawa-styles';
		style.textContent = `
			.wawa-stage { margin-top: 10px; }
			.wawa-screen {
				position: relative;
				margin: 0 auto;
				background-size: cover;
				background-position: center;
				overflow: hidden;
				border: 6px solid #111;
				border-radius: 10px;
				box-shadow: 0 0 0 2px #444, 0 10px 30px rgba(0,0,0,.5);
				image-rendering: auto;
				transition: box-shadow .15s;
			}
			.wawa-miss-flash { box-shadow: 0 0 0 4px #ff3b3b, 0 10px 30px rgba(0,0,0,.5) !important; }
			.wawa-hud {
				position: absolute; top: 0; left: 0; right: 0; z-index: 5;
				display: flex; justify-content: space-between; padding: 8px 14px;
				background: linear-gradient(rgba(0,0,0,.65), rgba(0,0,0,0));
				color: #fff; font-family: 'Courier New', monospace; font-weight: 700;
				letter-spacing: 1px; text-shadow: 0 1px 2px #000;
			}
			.wawa-lives { color: #ffd23f; letter-spacing: 3px; }
			.wawa-formation { position: absolute; left: 0; top: 0; }
			.wawa-enemy { position: absolute; text-align: center; }
			.wawa-enemy-badge { font-size: 20px; line-height: 1; margin-bottom: 2px; filter: drop-shadow(0 1px 2px #000); }
			.wawa-enemy-qr {
				background: #fff; padding: 4px; border-radius: 4px;
				box-shadow: 0 2px 6px rgba(0,0,0,.4);
				display: inline-block;
			}
			.wawa-enemy-code {
				margin-top: 2px; font-family: 'Courier New', monospace; font-size: 10px;
				color: #fff; background: rgba(0,0,0,.55); border-radius: 3px; padding: 1px 3px;
				white-space: nowrap;
			}
			.wawa-enemy-dead { animation: wawa-pop .4s ease-out forwards; }
			@keyframes wawa-pop {
				0% { transform: scale(1); opacity: 1; }
				60% { transform: scale(1.4); opacity: .7; }
				100% { transform: scale(0.2); opacity: 0; }
			}
			.wawa-player {
				position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%);
				color: #5ad1ff; font-size: 26px; text-shadow: 0 0 8px #5ad1ff;
				z-index: 4;
			}
			.wawa-laser {
				position: absolute; height: 3px; background: #5ad1ff;
				box-shadow: 0 0 8px 2px #5ad1ff; transform-origin: 0 50%;
				z-index: 3; border-radius: 2px;
			}
			.wawa-overlay {
				position: absolute; inset: 0; z-index: 10;
				display: none; align-items: center; justify-content: center;
				background: rgba(0,0,0,.72); color: #fff; text-align: center;
			}
			.wawa-overlay-visible { display: flex; }
			.wawa-overlay-inner h2 {
				font-family: 'Courier New', monospace; letter-spacing: 3px;
				color: #ffd23f; text-shadow: 0 0 10px rgba(255,210,63,.6);
			}
		`;
		document.head.appendChild(style);
	}
};
