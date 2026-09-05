import {
  useEffect,
  useRef,
} from "react";


/**
 * Repeatedly executes an async function.
 *
 * The callback is also executed immediately when
 * the component mounts.
 *
 * The interval is cleaned up automatically when
 * the component unmounts.
 */
export function usePolling(
  callback,
  interval = 3000,
  enabled = true
) {
  const callbackRef = useRef(
    callback
  );


  useEffect(() => {
    callbackRef.current =
      callback;
  }, [callback]);


  useEffect(() => {
    if (!enabled) {
      return undefined;
    }


    let cancelled = false;


    const execute = async () => {
      if (cancelled) {
        return;
      }


      try {
        await callbackRef.current();
      } catch (error) {
        console.error(
          "Polling error:",
          error
        );
      }
    };


    // Initial request
    execute();


    // Repeated requests
    const timer = setInterval(
      execute,
      interval
    );


    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [
    interval,
    enabled,
  ]);
}