/**
 * Local input profiles. Loaded after the editor bundle and before App.main,
 * so the same implementation is used by production and development builds.
 */
(function()
{
	var init = EditorUi.prototype.init;

	EditorUi.prototype.init = function()
	{
		init.apply(this, arguments);

		if (this.controlProfileInstalled || (this.editor.chromeless && !this.editor.editable))
		{
			return;
		}

		this.controlProfileInstalled = true;
		var ui = this;
		var graph = this.editor.graph;
		var rubberband = graph.getRubberband();
		var panning = graph.panningHandler;
		var zoomGesture = false;
		var panOrigin = null;
		var panMoved = false;
		var saved = (Editor.isSettingsEnabled() && mxSettings.settings != null) ?
			mxSettings.settings.controlProfile : null;
		this.controlProfile = (saved == 'visio') ? 'visio' : 'drawio';

		function active()
		{
			return ui.controlProfile == 'visio';
		}

		function updateHints()
		{
			if (ui.toolbar != null && ui.toolbar.container != null)
			{
				var elements = ui.toolbar.container.querySelectorAll('[title]');

				for (var i = 0; i < elements.length; i++)
				{
					var title = elements[i].getAttribute('title');

					if (elements[i].controlProfileTitle != null || title.indexOf('Alt+Mousewheel') >= 0)
					{
						elements[i].controlProfileTitle = elements[i].controlProfileTitle || title;
						elements[i].setAttribute('title', active() ?
							elements[i].controlProfileTitle.replace(/Alt\+Mousewheel/g, 'Ctrl+Mousewheel') :
							elements[i].controlProfileTitle);
					}
				}
			}
		}

		updateHints();

		function navigationEvent(evt)
		{
			// Visio documents the literal Ctrl key, including on macOS.
			return active() && mxEvent.isControlDown(evt) && mxEvent.isShiftDown(evt) &&
				!mxEvent.isAltDown(evt) && !mxEvent.isMetaDown(evt) &&
				!graph.isEditing() && (ui.dialogs == null || ui.dialogs.length == 0) &&
				(graph.freehand == null || !graph.freehand.isActive());
		}

		this.setControlProfile = function(profile)
		{
			if (profile != 'drawio' && profile != 'visio')
			{
				return;
			}

			rubberband.cancel();
			zoomGesture = false;
			panOrigin = null;
			panning.reset();
			ui.controlProfile = profile;
			updateHints();

			if (Editor.isSettingsEnabled() && mxSettings.settings != null)
			{
				mxSettings.settings.controlProfile = profile;
				mxSettings.save();
			}
		};

		var isZoomWheelEvent = graph.isZoomWheelEvent;
		graph.isZoomWheelEvent = function(evt)
		{
			return active() ? mxEvent.isControlDown(evt) :
				isZoomWheelEvent.apply(this, arguments);
		};

		var isForcePanningEvent = panning.isForcePanningEvent;
		panning.isForcePanningEvent = function(me)
		{
			var evt = me.getEvent();

			if (navigationEvent(evt))
			{
				if (mxEvent.isRightMouseButton(evt))
				{
					panOrigin = new mxPoint(me.getX(), me.getY());
					panMoved = false;
					return true;
				}
				else if (mxEvent.isLeftMouseButton(evt))
				{
					return false;
				}
			}

			return isForcePanningEvent.apply(this, arguments);
		};

		var panningMouseMove = panning.mouseMove;
		panning.mouseMove = function(sender, me)
		{
			if (panOrigin != null && (Math.abs(me.getX() - panOrigin.x) > graph.tolerance ||
				Math.abs(me.getY() - panOrigin.y) > graph.tolerance))
			{
				panMoved = true;
			}

			panningMouseMove.apply(this, arguments);
		};

		var panningReset = panning.reset;
		panning.reset = function()
		{
			panOrigin = null;
			panningReset.apply(this, arguments);
		};

		var panningMouseUp = panning.mouseUp;
		panning.mouseUp = function(sender, me)
		{
			var origin = panOrigin;
			var moved = panMoved;
			panOrigin = null;
			panningMouseUp.apply(this, arguments);

			if (origin != null && !moved && Math.abs(me.getX() - origin.x) <= graph.tolerance &&
				Math.abs(me.getY() - origin.y) <= graph.tolerance)
			{
				graph.zoomOut();
				me.consume();
			}
		};

		var isForceRubberbandEvent = rubberband.isForceRubberbandEvent;
		rubberband.isForceRubberbandEvent = function(me)
		{
			if (navigationEvent(me.getEvent()) && mxEvent.isLeftMouseButton(me.getEvent()))
			{
				zoomGesture = true;
				return true;
			}

			return isForceRubberbandEvent.apply(this, arguments);
		};

		var rubberbandMouseUp = rubberband.mouseUp;
		var rubberbandReset = rubberband.reset;
		rubberband.reset = function()
		{
			zoomGesture = false;
			rubberbandReset.apply(this, arguments);
		};

		rubberband.mouseUp = function(sender, me)
		{
			if (zoomGesture && this.first != null && !this.cancelled)
			{
				var end = mxUtils.convertPoint(graph.container, me.getX(), me.getY());
				var rect = new mxRectangle(Math.min(this.first.x, end.x),
					Math.min(this.first.y, end.y), Math.abs(end.x - this.first.x),
					Math.abs(end.y - this.first.y));
				zoomGesture = false;
				this.reset();

				if (rect.width > graph.tolerance && rect.height > graph.tolerance)
				{
					graph.zoomToRect(rect);
				}
				else
				{
					graph.zoomIn();
				}

				me.consume();
			}
			else
			{
				zoomGesture = false;
				rubberbandMouseUp.apply(this, arguments);
			}
		};

		var isPopupTrigger = graph.popupMenuHandler.isPopupTrigger;
		graph.popupMenuHandler.isPopupTrigger = function(me)
		{
			return !navigationEvent(me.getEvent()) && isPopupTrigger.apply(this, arguments);
		};

		var contextMenuListener = function(evt)
		{
			if (navigationEvent(evt))
			{
				mxEvent.consume(evt);
			}
		};
		mxEvent.addListener(graph.container, 'contextmenu', contextMenuListener);

		var getFunction = this.keyHandler.getFunction;
		this.keyHandler.getFunction = function(evt)
		{
			if (navigationEvent(evt) && evt.keyCode == 87)
			{
				return function() { ui.actions.get('fitWindow').funct(); };
			}

			return getFunction.apply(this, arguments);
		};

		var extras = this.menus.get('extras');
		var extrasFunct = extras.funct;
		extras.funct = function(menu, parent)
		{
			extrasFunct.apply(this, arguments);
			menu.addSeparator(parent);
			var submenu = menu.addItem(mxResources.get('controlProfile', null, 'Mouse controls'), null, null, parent);

			function addProfile(label, value)
			{
				var item = menu.addItem(label, null, function() { ui.setControlProfile(value); }, submenu);

				if (ui.controlProfile == value)
				{
					menu.addCheckmark(item, Editor.checkmarkImage);
				}
			}

			addProfile('draw.io', 'drawio');
			addProfile('Visio', 'visio');
		};

		var destroy = this.destroy;
		this.destroy = function()
		{
			mxEvent.removeListener(graph.container, 'contextmenu', contextMenuListener);
			destroy.apply(this, arguments);
		};
	};
})();
