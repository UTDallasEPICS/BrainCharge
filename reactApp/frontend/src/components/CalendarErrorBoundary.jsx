import { LanguageContext } from "../i18n/language.js";
import { Component } from "react";

export default class CalendarErrorBoundary extends Component {
  static contextType = LanguageContext;

  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    const { t } = this.context;
    if (this.state.error) {
      return (
        <div className="calendar-screen">
          <div className="calendar-header">
            <h1>{t("Calendar")}</h1>
            <p>{t("We couldn't load the calendar view.")}</p>
          </div>
          <div className="calendar-error">
            <p>{this.state.error.message || t("Something went wrong.")}</p>
            <button type="button" className="retry-btn" onClick={() => this.setState({ error: null })}>
              {t("Try again")}
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
