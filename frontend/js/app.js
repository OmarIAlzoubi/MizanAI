import {
    initDashboardLayout
} from "./ui/dashboardLayout.js";


import {
    initDashboard
} from "./dashboard.js";


import {
    initChat
} from "./chat.js?v=chat3";


async function start() {

    initDashboardLayout();

    initChat();

    await initDashboard();
}


start();