// background.js - Service Worker
console.log("Elnagar POS Extension: Service Worker Starting...");

chrome.runtime.onInstalled.addListener(() => {
    console.log("Elnagar POS Extension: Installed/Updated");
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
        .catch((error) => console.error(error));
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'open_side_panel') {
        // In MV3, we can only open side panel from user gesture.
        // However, if we are handling a message from content script *triggered* by user click,
        // we might be able to open it if the windowId is matched.
        if (sender.tab && sender.tab.windowId) {
            chrome.sidePanel.open({ windowId: sender.tab.windowId })
                .then(() => sendResponse({ success: true }))
                .catch((err) => {
                    console.error("Failed to open panel:", err);
                    sendResponse({ success: false, error: err.message });
                });
            return true; // Keep port open for async response
        }
    }
});

// Shortcut Command
chrome.commands.onCommand.addListener((command) => {
    if (command === 'toggle_side_panel') {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                chrome.sidePanel.open({ windowId: tabs[0].windowId });
            }
        });
    }
});
