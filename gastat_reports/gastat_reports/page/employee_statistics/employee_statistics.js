frappe.pages["employee-statistics"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("إحصاءات الموظفين"),
		single_column: true
	});
	$(frappe.render_template("employee_statistics")).appendTo(page.body);
	init_employee_statistics(page, $(page.body));
};

function init_employee_statistics(page, $page) {
	var state = { data: null, last: {} };
	var months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];

	var EMPLOYEE_COLUMNS = [
		{ key: "employee", label: "رقم الموظف", type: "text" },
		{ key: "national_id", label: "رقم الهوية", type: "text" },
		{ key: "employee_name", label: "اسم الموظف", type: "text" },
		{ key: "designation", label: "المسمى الوظيفي", type: "text" },
		{ key: "company", label: "الشركة", type: "text" },
		{ key: "payment_days", label: "ايام العمل", type: "num" },
		{ key: "basic", label: "الاساسي", type: "money" },
		{ key: "housing", label: "بدل السكن", type: "money" },
		{ key: "transportation", label: "بدل المواصلات", type: "money" },
		{ key: "allowances", label: "البدلات", type: "money" },
		{ key: "monthly_salary", label: "اجمالي الراتب", type: "money" },
		{ key: "total_transferred", label: "اجمالي الراتب المحول", type: "money" }
	];
	var SUMMARY_TOTAL_KEY = {
		basic: "total_basic", housing: "total_housing", transportation: "total_transportation",
		allowances: "total_allowances", monthly_salary: "total_salaries", total_transferred: "total_transferred"
	};
	var selectedCols = EMPLOYEE_COLUMNS.map(function (c) { return c.key; });

	// Build the column checkboxes + sort dropdown
	$page.find("#emp-cols").html(EMPLOYEE_COLUMNS.map(function (c) {
		return '<label class="ctl-col"><input type="checkbox" data-key="' + c.key + '" checked>' + c.label + "</label>";
	}).join(""));
	$page.find("#emp-cols-toggle").on("click", function () {
		var wrap = $page.find("#emp-cols-wrap");
		var open = wrap.is(":visible");
		wrap.toggle(!open);
		$page.find("#emp-cols-toggle .ctl-chevron").text(open ? "▾" : "▴");
	});
	$page.find("#emp-cols input").on("change", function () {
		selectedCols = $page.find("#emp-cols input:checked").map(function () { return $(this).data("key"); }).get();
		state.last.columns = JSON.stringify(selectedCols);
		if (state.data) { refreshTable(state.data); }
	});
	renderSelect($page.find("#emp-sort"), EMPLOYEE_COLUMNS.map(function (c) { return { value: c.key, label: c.label }; }), "employee");

	function renderSelect($el, items, selected) { $el.empty(); items.forEach(function (it) { $el.append($("<option>").val(it.value).text(it.label)); }); $el.val(selected); }

	var now = new Date();
	var yearOptions = [];
	for (var y = now.getFullYear(); y >= now.getFullYear() - 5; y--) yearOptions.push({ value: y, label: String(y) });
	renderSelect($page.find("#emp-year"), yearOptions, now.getFullYear());
	renderSelect($page.find("#emp-month"), months.map(function (m, i) { return { value: i + 1, label: m }; }), now.getMonth() + 1);
	$page.find("#emp-today-date").text(now.toLocaleDateString("ar-SA", { weekday: "long", year: "numeric", month: "long", day: "numeric" }));

	frappe.call({
		method: "gastat_reports.gastat_reports.page.employee_statistics.employee_statistics.get_company_list",
		callback: function (r) {
			var companies = r.message || [];
			renderSelect($page.find("#emp-company"), companies.map(function (c) { return { value: c[0], label: c[0] }; }), companies.length ? companies[0][0] : "");
			if (companies.length) generate();
		}
	});

	function currentParams() {
		return {
			company: $page.find("#emp-company").val(),
			month: $page.find("#emp-month").val(),
			year: $page.find("#emp-year").val(),
			sort_by: $page.find("#emp-sort").val(),
			sort_order: $page.find("#emp-sort-dir").val(),
			columns: JSON.stringify(selectedCols)
		};
	}

	function generate() {
		var params = currentParams();
		if (!params.company) { showError("لم يتم اختيار الشركة."); return; }
		state.last = params;
		showLoading(true);
		$page.find("#emp-pdf, #emp-xls").prop("disabled", true);
		frappe.call({
			method: "gastat_reports.gastat_reports.page.employee_statistics.employee_statistics.get_report",
			args: params,
			callback: function (r) {
				if (r && r.exc) { showError(extractError(r)); showLoading(false); return; }
				var d = gastat.processResponse(r);
				state.data = d;
				render(d);
				$page.find("#emp-pdf, #emp-xls").prop("disabled", false);
				showLoading(false);
			},
			error: function (r) { showError(extractError(r)); showLoading(false); }
		});
	}

	$page.find("#emp-generate").on("click", generate);
	$page.find("#emp-pdf").on("click", function () { doExport("pdf"); });
	$page.find("#emp-xls").on("click", function () { doExport("xls"); });
	$page.find("#emp-sort, #emp-sort-dir").on("change", function () { if (state.data) generate(); });

	function doExport(kind) {
		var p = state.last;
		frappe.call({
			method: kind === "pdf" ? "gastat_reports.api.export_employee_pdf" : "gastat_reports.api.export_employee_excel",
			args: p,
			callback: function (r) {
				if (r && r.exc) { frappe.msgprint({ message: extractError(r), indicator: "red", title: "خطأ" }); return; }
				gastat.download(r.message);
				frappe.show_alert({ message: "تم تصدير التقرير بنجاح", indicator: "green" });
			}
		});
	}

	function refreshTable(d) {
		var s = d.summary;
		var activeCols = EMPLOYEE_COLUMNS.filter(function (c) { return selectedCols.indexOf(c.key) !== -1; });
		var headers = ["الرقم"].concat(activeCols.map(function (c) { return c.label; }));

		var rowsHtml = d.total_rows.map(function (x, i) {
			var cells = "<td>" + (i + 1) + "</td>";
			activeCols.forEach(function (c) {
				var v = x[c.key];
				if (c.type === "money") {
					cells += "<td class='num'>" + gastat.formatNumber(v) + "</td>";
				} else if (c.type === "num") {
					cells += "<td class='num'>" + gastat.formatNumber(v) + "</td>";
				} else {
					cells += "<td>" + gastat.esc(v || "-") + "</td>";
				}
			});
			return "<tr>" + cells + "</tr>";
		}).join("");

		var moneyCols = activeCols.filter(function (c) { return c.type === "money"; });
		var textCount = activeCols.filter(function (c) { return c.type === "text"; }).length;
		var hasNum = activeCols.some(function (c) { return c.type === "num"; });
		var labelSpan = Math.max(1 + textCount, 1);
		var tail = "";
		if (hasNum) tail += "<td class='num'></td>";
		tail += moneyCols.map(function (c) {
			return "<td class='num'>" + gastat.formatNumber(s[SUMMARY_TOTAL_KEY[c.key]]) + "</td>";
		}).join("");

		var grandTotal = "<tr class='total-row'>" +
			"<td colspan='" + labelSpan + "'>الإجمالي الكلي</td>" + tail + "</tr>";

		$page.find("#emp-table").html(
			'<div class="table-header"><h3>تفاصيل الموظفين</h3><span class="count-pill">' + s.total_employees + " موظف</span></div>" +
			'<div class="gastat-table-resp">' +
			'<table class="gastat-table"><thead><tr>' +
			headers.map(function (h) { return "<th>" + h + "</th>"; }).join("") +
			"</tr></thead><tbody>" + rowsHtml + grandTotal + "</tbody></table></div>"
		);
	}

	function render(d) {
		var s = d.summary;
		$page.find("#emp-period-label").text(s.month_name_ar + " " + s.year + " | " + (s.salary_col || ""));

		var cards = [
			{ c: "c-green", icon: "percent", label: "نسبة السعوديين", value: s.saudi_pct + "%", sub: "من " + gastat.formatNumber(s.total_employees) + " موظف" },
			{ c: "c-purple", icon: "percent", label: "نسبة غير السعوديين", value: s.nonsaudi_pct + "%", sub: "من " + gastat.formatNumber(s.total_employees) + " موظف" },
			{ c: "c-green", icon: "male", label: "سعوديون (ذكور)", value: gastat.formatNumber(s.saudi_male) },
			{ c: "c-pink", icon: "female", label: "سعوديات (إناث)", value: gastat.formatNumber(s.saudi_female) },
			{ c: "c-blue", icon: "male", label: "غير سعوديين (ذكور)", value: gastat.formatNumber(s.nonsaudi_male) },
			{ c: "c-purple", icon: "female", label: "غير سعوديات (إناث)", value: gastat.formatNumber(s.nonsaudi_female) },
			{ c: "c-green", icon: "currency", label: "إجمالي رواتب السعوديين", value: gastat.formatNumber(s.saudi_salaries, s.currency) },
			{ c: "c-purple", icon: "currency", label: "إجمالي رواتب غير السعوديين", value: gastat.formatNumber(s.nonsaudi_salaries, s.currency) }
		];
		$page.find("#emp-cards").html(cards.map(function (c) {
			return '<div class="gstat-card ' + c.c + '"><div class="icon">' + gastat.icons[c.icon] + '</div>' +
				'<div><div class="c-label">' + c.label + '</div><div class="c-value">' + c.value + '</div>' +
				(c.sub ? '<div class="c-sub">' + c.sub + '</div>' : '') + '</div></div>';
		}).join(""));

		var charts = d.charts || {};
		var chartBox = function (title, id, chartData, type) {
			return '<div class="gastat-chart-box" style="min-width:280px;"><h3>' + title + '</h3><div class="chart-wrap" id="' + id + '"></div></div>';
		};
		var html =
			(charts.saudi_vs_nonsaudi ? chartBox("التوزيع: سعودي / غير سعودي", "emp-chart-sn", charts.saudi_vs_nonsaudi, "pie") : "") +
			(charts.male_vs_female ? chartBox("التوزيع: ذكور / إناث", "emp-chart-mf", charts.male_vs_female, "pie") : "") +
			(charts.salary_by_category ? chartBox("الرواتب حسب الفئة", "emp-chart-sal", charts.salary_by_category, "bar") : "");
		$page.find("#emp-charts").html(html);

		function makeChart(id, ch, type) {
			var el = document.getElementById(id);
			if (!el || !ch || !ch.values || !ch.values.length) return;
			var opts = {
				data: { labels: ch.labels, datasets: [{ values: ch.values }] },
				type: type,
				height: 300,
				colors: ch.colors || ["#0f766e", "#7c3aed"],
				axisOptions: { xAxisMode: "tick", yAxisMode: "tick", xAxisLabelOversizeValidation: true }
			};
			if (type === "bar") {
				opts.barOptions = { spaceRatio: 0.5, barRadius: 6 };
			}
			new frappe.Chart(el, opts);
		}
		setTimeout(function () {
			makeChart("emp-chart-sn", charts.saudi_vs_nonsaudi, "pie");
			makeChart("emp-chart-mf", charts.male_vs_female, "pie");
			makeChart("emp-chart-sal", charts.salary_by_category, "bar");
		}, 50);

		refreshTable(d);

		$page.find("#emp-empty").hide();
		$page.find("#emp-cards, #emp-charts, #emp-table").show();
	}

	function showLoading(v) { $page.find("#emp-loading").css("display", v ? "flex" : "none"); }
	function showError(msg) {
		$page.find("#emp-cards, #emp-charts, #emp-table").hide();
		$page.find("#emp-empty").show();
		$page.find("#emp-error").text(msg || "حدث خطأ أثناء توليد التقرير.");
	}
	function extractError(r) {
		try { var e = JSON.parse(r._server_messages); return JSON.parse(e[0]).message || "خطأ غير معروف"; }
		catch (err) { return "خطأ غير معروف"; }
	}
}
