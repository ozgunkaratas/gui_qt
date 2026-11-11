#include <QApplication>

#include "model.h"
#include "view.h"

int main(int argc, char* argv[])
{
    QApplication app(argc, argv);
    // We decide ourselves when to quit (via View::finished), instead of
    // relying on "last window closed" while dialogs come and go.
    app.setQuitOnLastWindowClosed(false);

    Model model;   // logic
    View  view;    // presentation

    // ---- The wiring. This is the only place that knows both sides exist. ----

    // View -> Model: the user submitted some text, please evaluate it.
    QObject::connect(&view, &View::numberSubmitted, &model, &Model::evaluate);

    // Model -> View: the outcome of the evaluation.
    QObject::connect(&model, &Model::invalidInput, &view, &View::showInvalidInput);
    QObject::connect(&model, &Model::resultReady,  &view, &View::showResult);

    // View -> application: the user is done.
    QObject::connect(&view, &View::finished, &app, &QApplication::quit);

    view.start();
    return app.exec();
}
