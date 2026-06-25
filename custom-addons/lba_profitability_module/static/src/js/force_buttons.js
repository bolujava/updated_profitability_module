odoo.define('lba_profitability_module.force_buttons', function(require) {
    "use strict";

    var FormController = require('web.FormController');
    var core = require('web.core');

    FormController.include({
        _onViewRendered: function() {
            this._super.apply(this, arguments);

            // Force show all accept/decline buttons
            var self = this;
            setTimeout(function() {
                // Find all accept and decline buttons
                var buttons = document.querySelectorAll('button[name="accept_department_manager"], button[name="accept_team_lead"], button[name="accept_project_manager"]');

                buttons.forEach(function(button) {
                    // Remove invisible attribute and class
                    button.removeAttribute('invisible');
                    button.classList.remove('o_invisible_modifier');
                    button.style.display = 'inline-block';
                    button.style.visibility = 'visible';
                    console.log('Button forced visible:', button.getAttribute('name'));
                });
            }, 100);
        }
    });
});