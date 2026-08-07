/**
 * OPT-P1-11 标签输入交互 — inline chip 模式。
 *
 * 页面须包含：
 *   .tag-input-wrapper  — 外层容器（模拟输入框）
 *   #tags_input          — 实际文本输入（无 border，嵌在容器内）
 *   input[name="tags"]   — 隐藏字段，逗号分隔同步所有标签
 *   #tag-suggest         — 自动补全下拉
 */
(function () {
    var $wrapper = $('.tag-input-wrapper');
    var $input = $('#tags_input');
    if (!$wrapper.length || !$input.length) return;

    var $suggest = $('#tag-suggest');
    var $hidden = $wrapper.closest('form').find('input[type="hidden"][name="tags"]');
    if (!$hidden.length) {
        $hidden = $('<input type="hidden" name="tags">');
        $wrapper.closest('form').append($hidden);
    }
    var tags = [];
    var suggestTimer = null;

    // 初始化：从 hidden 值解析已有标签
    var initVal = ($hidden.val() || '').trim();
    if (initVal) {
        initVal.split(',').forEach(function (t) {
            t = t.trim();
            if (t && tags.indexOf(t) === -1) tags.push(t);
        });
        renderChips();
    }

    function syncHidden() {
        $hidden.val(tags.join(','));
    }

    function createChipEl(tag, idx) {
        var $chip = $('<span class="tag-chip"></span>');
        $chip.append($('<span class="tag-chip-text"></span>').text(tag));
        var $x = $('<a href="javascript:;" class="tag-chip-remove">&times;</a>');
        $x.on('click', function (e) {
            e.stopPropagation();
            tags.splice(idx, 1);
            renderChips();
            $input.focus();
        });
        $chip.append($x);
        return $chip;
    }

    function renderChips() {
        $wrapper.find('.tag-chip').remove();
        for (var i = 0; i < tags.length; i++) {
            $input.before(createChipEl(tags[i], i));
        }
        syncHidden();
    }

    function addTag(name) {
        name = (name || '').trim();
        if (!name) return;
        if (tags.indexOf(name) !== -1) return;
        tags.push(name);
        renderChips();
        $input.val('');
        $suggest.hide();
    }

    // 点击 wrapper → focus 输入
    $wrapper.on('click', function (e) {
        if (!$(e.target).is('a')) $input.focus();
    });

    // 输入事件 — 自动补全
    $input.on('input', function () {
        clearTimeout(suggestTimer);
        var q = $input.val().trim();
        if (q.length < 1) {
            $suggest.hide();
            return;
        }
        suggestTimer = setTimeout(function () {
            var params = { q: q };
            var $gidSelect = $('select[name="group_id"]');
            if ($gidSelect.length && $gidSelect.val()) {
                params.group_id = $gidSelect.val();
            }
            $.getJSON('/api/tags/suggest', params, function (data) {
                if (!data || !data.length) {
                    $suggest.hide();
                    return;
                }
                $suggest.empty();
                data.forEach(function (item) {
                    var tagName = typeof item === 'string' ? item : item.name;
                    var desc = (typeof item === 'object' && item.description) ? item.description : '';
                    if (tags.indexOf(tagName) !== -1) return;
                    var $item = $('<div class="tag-suggest-item"></div>');
                    var label = tagName;
                    if (desc) label += ' — ' + desc;
                    $item.text(label);
                    $item.on('mousedown', function (e) {
                        e.preventDefault();
                        addTag(tagName);
                    });
                    $suggest.append($item);
                });
                if ($suggest.children().length) {
                    $suggest.show();
                } else {
                    $suggest.hide();
                }
            });
        }, 200);
    });

    // Enter / 逗号 / 空格 → 添加标签
    $input.on('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ',' || e.key === ' ') {
            var val = $input.val().replace(/,/g, '').trim();
            if (val) {
                e.preventDefault();
                addTag(val);
                // 防御：部分浏览器 preventDefault 对可打印字符不完全生效，
                // 延迟清除确保浏览器完成字符插入后再清空
                setTimeout(function () { $input.val(''); }, 0);
            } else if (e.key === 'Enter') {
                e.preventDefault();
            }
        }
        // Backspace 空输入 → 删除最后一个 chip
        if (e.key === 'Backspace' && !$input.val()) {
            if (tags.length) {
                tags.pop();
                renderChips();
            }
        }
    });

    // 失去焦点时添加当前输入
    $input.on('blur', function () {
        setTimeout(function () {
            $suggest.hide();
            var val = $input.val().replace(/,/g, '').trim();
            if (val) addTag(val);
        }, 150);
    });
})();
