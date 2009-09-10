import wx

class Frame(wx.Frame):

    def __init__(self):
        wx.Frame.__init__(self, parent = None, title = "Hello from cx_Freeze")
        panel = wx.Panel(self)
        closeMeButton = wx.Button(panel, -1, "Close Me")
        wx.EVT_BUTTON(self, closeMeButton.GetId(), self.OnCloseMe)
        wx.EVT_CLOSE(self, self.OnCloseWindow)
        pushMeButton = wx.Button(panel, -1, "Push Me")
        wx.EVT_BUTTON(self, pushMeButton.GetId(), self.OnPushMe)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(closeMeButton, flag = wx.ALL, border = 20)
        sizer.Add(pushMeButton, flag = wx.ALL, border = 20)
        panel.SetSizer(sizer)
        topSizer = wx.BoxSizer(wx.VERTICAL)
        topSizer.Add(panel, flag = wx.ALL | wx.EXPAND)
        topSizer.Fit(self)

    def OnCloseMe(self, event):
        self.Close(True)

    def OnPushMe(self, event):
        1 / 0

    def OnCloseWindow(self, event):
        self.Destroy()


class App(wx.App):

    def OnInit(self):
        frame = Frame()
        frame.Show(True)
        self.SetTopWindow(frame)
        return True


app = App(1)
app.MainLoop()

