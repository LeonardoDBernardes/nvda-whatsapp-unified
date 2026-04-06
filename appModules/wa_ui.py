# -*- coding: UTF-8 -*-
"""Interface visual: janela de texto para leitura de mensagens."""

import wx
import gui


class TextWindow(wx.Frame):
    """Janela de texto acessível para leitura de mensagens longas."""

    def __init__(self, text, title="Mensagem"):
        super().__init__(gui.mainFrame, title=title)
        sizer = wx.BoxSizer(wx.VERTICAL)
        style = wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH | wx.TE_AUTO_URL
        self.ctrl = wx.TextCtrl(self, style=style)
        self.ctrl.Bind(wx.EVT_KEY_DOWN, self._onKey)
        sizer.Add(self.ctrl, proportion=1, flag=wx.EXPAND)
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.ctrl.SetValue(text)
        self.ctrl.SetFocus()
        self.ctrl.SetInsertionPoint(0)
        self.Raise()
        self.Maximize()
        self.Show()

    def _onKey(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        event.Skip()
