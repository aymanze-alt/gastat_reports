frappe.pages["production-survey"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("المسح الصناعي الشهري"),
		single_column: true
	});
	$(frappe.render_template("production_survey")).appendTo(page.body);
	init_production_survey(page, $(page.body));
};

function init_production_survey(page, $page) {
	var state = { data: null, last: {} };
	var months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];

	function renderSelect($el, items, selected) {
		$el.empty();
		items.forEach(function (it) {
			$el.append($("<option>").val(it.value).text(it.label));
		});
		$el.val(selected);
	}

	// fill year + month
	var now = new Date();
	var yearOptions = [];
	for (var y = now.getFullYear(); y >= now.getFullYear() - 5; y--) yearOptions.push({ value: y, label: String(y) });
	renderSelect($page.find("#prod-year"), yearOptions, now.getFullYear());

	var curMonth = now.getMonth(); // 0-based
	renderSelect(
		$page.find("#prod-month"),
		months.map(function (m, i) { return { value: i + 1, label: m }; }),
		curMonth + 1
	);

	$page.find("#prod-today-date").text(now.toLocaleDateString("ar-SA", { weekday: "long", year: "numeric", month: "long", day: "numeric" }));

	// company list
	frappe.call({
		method: "gastat_reports.gastat_reports.page.production_survey.production_survey.get_company_list",
		callback: function (r) {
			var companies = r.message || [];
			renderSelect(
				$page.find("#prod-company"),
				companies.map(function (c) { return { value: c[0], label: c[0] }; }),
				companies.length ? companies[0][0] : ""
			);
			if (companies.length) generate();
		}
	});

	function currentParams() {
		return {
			company: $page.find("#prod-company").val(),
			month: $page.find("#prod-month").val(),
			year: $page.find("#prod-year").val()
		};
	}

	function generate() {
		var params = currentParams();
		if (!params.company) { showError("لم يتم اختيار الشركة."); return; }
		state.last = params;
		showLoading(true);
		$page.find("#prod-pdf, #prod-xls").prop("disabled", true);
		frappe.call({
			method: "gastat_reports.gastat_reports.page.production_survey.production_survey.get_report",
			args: params,
			callback: function (r) {
				var d = gastat.processResponse(r);
				if (r && r.exc) { showError(extractError(r)); showLoading(false); return; }
				state.data = d;
				render(d);
				$page.find("#prod-pdf, #prod-xls").prop("disabled", false);
				showLoading(false);
			},
			error: function (r) { showError(extractError(r)); showLoading(false); }
		});
	}

	$page.find("#prod-generate").on("click", generate);
	$page.find("#prod-pdf").on("click", function () { doExport("pdf"); });
	$page.find("#prod-xls").on("click", function () { doExport("xls"); });

	function doExport(kind) {
		var p = state.last;
		frappe.call({
			method: kind === "pdf"
				? "gastat_reports.api.export_production_pdf"
				: "gastat_reports.api.export_production_excel",
			args: { company: p.company || "", month: p.month, year: p.year },
			callback: function (r) {
				if (r && r.exc) { frappe.msgprint({ message: extractError(r), indicator: "red", title: "خطأ" }); return; }
				var url = r.message;
				gastat.download(url);
				frappe.show_alert({ message: "تم تصدير التقرير بنجاح", indicator: "green" });
			}
		});
	}

	function render(d) {
		var s = d.summary;
		$page.find("#prod-period-label").text(s.month_name_ar + " " + s.year);

		// cards
		var cards = [
			{ c: "c-blue", icon: "package", label: "عدد الأصناف المنتجة", value: gastat.formatNumber(s.total_items) },
			{ c: "c-green", icon: "layers", label: "إجمالي الكمية (الصافي)", value: gastat.formatNumber(s.total_qty) },
			{ c: "c-orange", icon: "speed", label: "متوسط سعر الوحدة", value: gastat.formatNumber(s.avg_unit_price, s.currency) },
			{ c: "c-purple", icon: "currency", label: "إجمالي قيمة الإنتاج (الصافي)", value: gastat.formatNumber(s.total_value, s.currency) }
		];
		if (s.returns_value) {
			cards.push({ c: "c-rose", icon: "arrow-down", label: "خصم المرتجعات", value: gastat.formatNumber(s.returns_value, s.currency) });
		}
		$page.find("#prod-cards").html(
			cards.map(function (c) {
				return '<div class="gstat-card ' + c.c + '"><div class="icon">' + gastat.icons[c.icon] + '</div>' +
					'<div><div class="c-label">' + c.label + '</div><div class="c-value">' + c.value + '</div>' +
					'<div class="c-sub">مصدر البيانات: ' + gastat.esc(s.production_source || "-") + ' | مصدر الأسعار: ' + gastat.esc(s.price_source) + '</div></div></div>';
			}).join("")
		);

		// chart
		var chartHtml = '<div class="gastat-chart-box"><h3>قيمة الإنتاج حسب الصنف (أعلى 12)</h3><div class="chart-wrap" id="prod-chart"></div></div>';
		$page.find("#prod-charts").html(chartHtml);
		if (d.chart && d.chart.values && d.chart.values.length) {
			new frappe.Chart("#prod-chart", {
				data: { labels: d.chart.labels, datasets: [{ values: d.chart.values }] },
				type: "bar",
				height: 320,
				colors: ["#14b8a6"],
				barOptions: { spaceRatio: 0.42, barRadius: 6 },
				axisOptions: { xAxisMode: "tick", yAxisMode: "tick", xAxisLabelOversizeValidation: true }
			});
		}

		// table
		var rowsHtml = d.rows.map(function (r) {
			return "<tr>" +
				"<td>" + r.sr + "</td>" +
				"<td><b>" + gastat.esc(r.item_code) + "</b></td>" +
				"<td>" + gastat.esc(r.item_name) + "</td>" +
				"<td>" + gastat.esc(r.hs_code || "-") + "</td>" +
				"<td class='num'>" + gastat.formatNumber(r.qty) + "</td>" +
				"<td>" + gastat.esc(r.uom) + "</td>" +
				"<td class='num'>" + gastat.formatNumber(r.unit_price) + "</td>" +
				"<td class='num'>" + gastat.formatNumber(r.total_value) + "</td>" +
				"</tr>";
		}).join("");

		var totalQty = d.rows.reduce(function (a, r) { return a + r.qty; }, 0);
		var totalVal = d.rows.reduce(function (a, r) { return a + r.total_value; }, 0);
		var retQty = s.returns_qty || 0;
		var retVal = s.returns_value || 0;
		var retRow = (retVal !== 0) ?
			"<tr style='background:#fff7ed;color:#c2410c;font-weight:600'>" +
			"<td colspan='4'>خصم المرتجعات / Less: Returns</td><td class='num'>" + gastat.formatNumber(retQty) + "</td><td></td><td></td>" +
			"<td class='num'>" + gastat.formatNumber(retVal, s.currency) + "</td></tr>" : "";
		var netRow = "<tr class='total-row'><td colspan='4'>الصافي / Net Total</td><td class='num'>" + gastat.formatNumber(s.total_qty) + "</td><td></td><td></td>" +
			"<td class='num'>" + gastat.formatNumber(s.total_value, s.currency) + "</td></tr>";

		$page.find("#prod-table").html(
			'<div class="table-header"><h3>تفاصيل الإنتاج حسب الصنف</h3><span class="count-pill">' + d.rows.length + " صنف</span></div>" +
			'<div class="gastat-table-resp">' +
			'<table class="gastat-table">' +
			"<thead><tr>" +
			"<th>#</th><th>كود الصنف</th><th>اسم الصنف</th><th>رمز HS</th><th>الكمية المنتجة</th><th>وحدة القياس</th><th>سعر الوحدة</th><th>القيمة الإجمالية</th>" +
			"</tr></thead><tbody>" +
			rowsHtml +
			"<tr class='total-row'><td colspan='4'>إجمالي المبيعات / Gross Total</td><td class='num'>" + gastat.formatNumber(totalQty) + "</td><td></td><td></td>" +
			"<td class='num'>" + gastat.formatNumber(totalVal, s.currency) + "</td></tr>" +
			retRow +
			netRow +
			"</tbody></table></div>"
		);

		$page.find("#prod-empty").hide();
		$page.find("#prod-cards, #prod-charts, #prod-table").show();
	}

	function showLoading(v) { $page.find("#prod-loading").css("display", v ? "flex" : "none"); }
	function showError(msg) {
		$page.find("#prod-cards, #prod-charts, #prod-table").hide();
		$page.find("#prod-empty").show();
		$page.find("#prod-error").text(msg || "حدث خطأ أثناء توليد التقرير.");
	}
	function extractError(r) {
		try {
			var e = JSON.parse(r._server_messages);
			return (JSON.parse(e[0]).message) || "خطأ غير معروف";
		} catch (err) { return (r && r._server_messages) ? "حدث خطأ أثناء التوليد" : "خطأ غير معروف"; }
	}
}
